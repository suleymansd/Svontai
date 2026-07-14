"""
AI Service for generating bot responses using OpenAI with guardrails and safety features.
"""

import re
from typing import Optional
from datetime import datetime, timedelta
from app.core.time import utc_now_naive
from collections import defaultdict

from openai import AsyncOpenAI

from app.core.config import settings
from app.models.bot import Bot
from app.models.knowledge import BotKnowledgeItem
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.bot_settings import BotSettings, ResponseTone, EmojiUsage


# In-memory rate limiting (use Redis in production)
_rate_limits = defaultdict(list)


class AIService:
    """Service for AI-powered response generation with guardrails."""
    
    def __init__(self):
        """Initialize the OpenAI client."""
        self.client: Optional[AsyncOpenAI] = None
        if settings.OPENAI_API_KEY.strip():
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        
        # Default safety settings
        self.default_guardrails = {
            "enable_guardrails": True,
            "uncertainty_threshold": 0.7,
            "prohibited_topics": [
                "illegal activities",
                "violence", 
                "adult content",
                "medical advice",
                "financial advice",
                "legal advice"
            ]
        }

    def _get_client(self) -> AsyncOpenAI:
        """Return the configured client without breaking non-AI application flows."""
        if self.client is None:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        return self.client
    
    def _get_tone_instructions(self, tone: str) -> str:
        """Get tone-specific instructions."""
        tone_map = {
            ResponseTone.FORMAL.value: "Resmi ve profesyonel bir dil kullan. Saygılı hitap et.",
            ResponseTone.FRIENDLY.value: "Samimi ve sıcak bir dil kullan. Arkadaşça konuş.",
            ResponseTone.PROFESSIONAL.value: "Profesyonel ama samimi bir dil kullan.",
            ResponseTone.CASUAL.value: "Rahat ve günlük bir dil kullan."
        }
        return tone_map.get(tone, tone_map[ResponseTone.FRIENDLY.value])
    
    def _get_emoji_instructions(self, emoji_usage: str) -> str:
        """Get emoji usage instructions."""
        emoji_map = {
            EmojiUsage.OFF.value: "Emoji kullanma.",
            EmojiUsage.LIGHT.value: "Nadiren emoji kullan, sadece uygun yerlerde (😊, 👍 gibi).",
            EmojiUsage.NORMAL.value: "Uygun yerlerde emoji kullan.",
            EmojiUsage.HEAVY.value: "Bol bol emoji kullan, mesajları renklendir."
        }
        return emoji_map.get(emoji_usage, emoji_map[EmojiUsage.LIGHT.value])
    
    def _build_system_prompt(
        self, 
        bot: Bot, 
        knowledge_items: list[BotKnowledgeItem],
        bot_settings: Optional[BotSettings] = None
    ) -> str:
        """
        Build the system prompt with bot context, knowledge base, and safety guardrails.
        """
        # Get settings
        tone = bot_settings.response_tone if bot_settings else ResponseTone.FRIENDLY.value
        emoji = bot_settings.emoji_usage if bot_settings else EmojiUsage.LIGHT.value
        enable_guardrails = bot_settings.enable_guardrails if bot_settings else True
        fallback_msg = bot_settings.fallback_message if bot_settings else "Üzgünüm, bu konuda size yardımcı olamıyorum."
        handoff_msg = bot_settings.human_handoff_message if bot_settings else "Sizi bir müşteri temsilcimize bağlıyorum."
        prohibited = bot_settings.prohibited_topics if bot_settings else self.default_guardrails["prohibited_topics"]
        custom_prompt = bot_settings.system_prompt_override if bot_settings else None
        
        # Base prompt
        if custom_prompt:
            base_prompt = custom_prompt + "\n\n"
        else:
            base_prompt = f"""Sen "{bot.name}" adlı işletmenin müşteri destek AI asistanısın.
{f"İşletme Açıklaması: {bot.description}" if bot.description else ""}

"""
        
        # Add tone and emoji instructions
        base_prompt += f"""
### KONUŞMA TARZI
{self._get_tone_instructions(tone)}
{self._get_emoji_instructions(emoji)}

### TEMEL KURALLAR
1. SADECE aşağıdaki bilgi tabanına dayanarak cevap ver.
2. Bilgi tabanında olmayan konularda "Maalesef bu konuda bilgim yok" de.
3. Fiyat, tarih, adres gibi spesifik bilgileri TAHMİN ETME, sadece bilgi tabanındakileri söyle.
4. Kısa ve net cevaplar ver (maksimum 2-3 cümle).
5. Her zaman nazik ve yardımsever ol.
6. Dil: Türkçe (kullanıcı farklı dilde yazarsa o dilde cevap ver)

"""
        
        # Add guardrails
        if enable_guardrails:
            base_prompt += f"""
### GÜVENLİK KURALLARI
- Yasaklı konular: {', '.join(prohibited)}
- Yasaklı konularda: "{fallback_msg}"
- Emin olmadığın konularda: "{handoff_msg}"
- Kişisel bilgi (TC, şifre vb.) ASLA isteme
- Fiyatları tahmini verme, bilgi tabanından al
- Politik, dini, ırkçı konulara girme

"""
        
        # Add knowledge base
        base_prompt += """
### BİLGİ TABANI
"""
        if knowledge_items:
            for item in knowledge_items:
                base_prompt += f"""
---
📌 {item.title}
S: {item.question}
C: {item.answer}
"""
        else:
            base_prompt += "\n(Henüz bilgi tabanı eklenmemiş. Genel bilgilerle yardımcı ol.)\n"
        
        return base_prompt
    
    def _build_conversation_context(
        self, 
        messages: list[Message], 
        max_messages: int = 10
    ) -> list[dict]:
        """Build conversation history for context with memory window."""
        context = []
        recent_messages = messages[-max_messages:] if len(messages) > max_messages else messages
        
        for msg in recent_messages:
            role = "assistant" if msg.sender == "bot" else "user"
            context.append({
                "role": role,
                "content": msg.content
            })
        
        return context
    
    def _check_rate_limit(
        self, 
        conversation_id: str,
        rate_per_minute: int = 20,
        rate_per_hour: int = 100
    ) -> tuple[bool, str]:
        """
        Check if conversation is rate limited.
        Returns (allowed: bool, message: str)
        """
        now = utc_now_naive()
        key = str(conversation_id)
        
        # Clean old entries
        _rate_limits[key] = [
            ts for ts in _rate_limits[key] 
            if ts > now - timedelta(hours=1)
        ]
        
        # Check limits
        minute_ago = now - timedelta(minutes=1)
        recent_minute = len([ts for ts in _rate_limits[key] if ts > minute_ago])
        recent_hour = len(_rate_limits[key])
        
        if recent_minute >= rate_per_minute:
            return False, "Çok fazla mesaj gönderdiniz. Lütfen biraz bekleyin."
        
        if recent_hour >= rate_per_hour:
            return False, "Saatlik mesaj limitinize ulaştınız. Lütfen daha sonra tekrar deneyin."
        
        # Record this request
        _rate_limits[key].append(now)
        
        return True, "OK"
    
    def _check_prohibited_content(
        self, 
        message: str,
        prohibited_topics: list[str]
    ) -> bool:
        """Check if message contains prohibited content."""
        message_lower = message.lower()
        
        # Simple keyword check (can be enhanced with AI classification)
        prohibited_keywords = {
            "illegal activities": ["illegal", "yasadışı", "kaçak", "uyuşturucu", "silah"],
            "violence": ["öldür", "şiddet", "dövme", "saldırı", "tehdit"],
            "adult content": ["porno", "seks", "cinsel", "erotik", "çıplak"],
            "medical advice": ["ilaç", "hastalık tedavisi", "doktor yerine"],
            "financial advice": ["yatırım tavsiyesi", "borsa", "kripto"],
            "legal advice": ["dava", "avukat yerine", "hukuki tavsiye"]
        }
        
        for topic in prohibited_topics:
            keywords = prohibited_keywords.get(topic, [])
            if any(kw in message_lower for kw in keywords):
                return True
        
        return False
    
    async def generate_reply(
        self,
        bot: Bot,
        knowledge_items: list[BotKnowledgeItem],
        conversation: Conversation,
        last_user_message: str,
        bot_settings: Optional[BotSettings] = None
    ) -> str:
        """
        Generate an AI response with guardrails and safety features.
        """
        # Get settings
        settings_obj = bot_settings or BotSettings()
        enable_guardrails = settings_obj.enable_guardrails if bot_settings else True
        fallback_msg = settings_obj.fallback_message if bot_settings else "Üzgünüm, bu konuda size yardımcı olamıyorum. Lütfen bizimle iletişime geçin."
        handoff_msg = settings_obj.human_handoff_message if bot_settings else "Sizi bir müşteri temsilcimize bağlıyorum. Lütfen bekleyin."
        memory_window = settings_obj.memory_window if bot_settings else 10
        max_tokens = settings_obj.max_response_length if bot_settings else 500
        rate_per_minute = settings_obj.rate_limit_per_minute if bot_settings else 20
        rate_per_hour = settings_obj.rate_limit_per_hour if bot_settings else 100
        prohibited = settings_obj.prohibited_topics if bot_settings else []
        
        # Check rate limit
        allowed, rate_msg = self._check_rate_limit(
            str(conversation.id),
            rate_per_minute,
            rate_per_hour
        )
        if not allowed:
            return rate_msg
        
        # Check prohibited content
        if enable_guardrails and self._check_prohibited_content(last_user_message, prohibited):
            return fallback_msg
        
        # Build system prompt
        system_prompt = self._build_system_prompt(bot, knowledge_items, bot_settings)
        
        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation context with memory window
        if conversation.messages:
            context = self._build_conversation_context(conversation.messages, memory_window)
            messages.extend(context)
        
        # Add current user message
        messages.append({"role": "user", "content": last_user_message})
        
        try:
            response = await self._get_client().chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
                presence_penalty=0.1,
                frequency_penalty=0.1
            )
            
            reply = response.choices[0].message.content or fallback_msg
            
            # Post-process: Check if response indicates uncertainty
            uncertainty_phrases = [
                "bilmiyorum", "emin değilim", "bilgim yok",
                "size yardımcı olamıyorum", "net bir cevap",
                "maalesef"
            ]
            
            if enable_guardrails:
                reply_lower = reply.lower()
                uncertainty_count = sum(1 for phrase in uncertainty_phrases if phrase in reply_lower)
                
                # If AI seems very uncertain, suggest human handoff
                if uncertainty_count >= 2:
                    reply += f"\n\n💬 {handoff_msg}"
            
            return reply
        
        except Exception as e:
            # Log the error
            print(f"OpenAI API error: {e}")
            return "Üzgünüm, şu anda yanıt veremiyorum. Lütfen daha sonra tekrar deneyin veya bizimle iletişime geçin."
    
    async def generate_summary(
        self,
        messages: list[Message],
        max_length: int = 100
    ) -> str:
        """Generate a summary of the conversation."""
        if not messages:
            return ""
        
        # Build conversation text
        conversation_text = "\n".join([
            f"{'Müşteri' if msg.sender == 'user' else 'Asistan'}: {msg.content}"
            for msg in messages[-20:]  # Last 20 messages
        ])
        
        try:
            response = await self._get_client().chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": f"Bu konuşmayı {max_length} karakterde özetle. Türkçe yaz."
                    },
                    {
                        "role": "user",
                        "content": conversation_text
                    }
                ],
                max_tokens=100,
                temperature=0.3
            )
            
            return response.choices[0].message.content or ""
        
        except Exception as e:
            print(f"Summary generation error: {e}")
            return ""


# Singleton instance
ai_service = AIService()
