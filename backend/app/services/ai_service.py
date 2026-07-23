"""Provider-neutral AI responses with guardrails and safety features."""

import logging
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

logger = logging.getLogger(__name__)

# In-memory rate limiting (use Redis in production)
_rate_limits = defaultdict(list)


class AIService:
    """Service for AI-powered response generation with guardrails."""
    
    def __init__(self):
        """Initialize the selected OpenAI-compatible provider client."""
        self.client: Optional[AsyncOpenAI] = None
        self.provider = settings.AI_PROVIDER
        if settings.ai_api_key:
            client_options = {
                "api_key": settings.ai_api_key,
                "timeout": settings.AI_REQUEST_TIMEOUT_SECONDS,
                "max_retries": settings.AI_REQUEST_MAX_RETRIES,
            }
            if settings.ai_base_url:
                client_options["base_url"] = settings.ai_base_url
            self.client = AsyncOpenAI(**client_options)
        self.model = settings.ai_model
        
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
            required_key = "GEMINI_API_KEY" if self.provider == "gemini" else "OPENAI_API_KEY"
            raise RuntimeError(f"{required_key} is not configured")
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
        bot_settings: Optional[BotSettings] = None,
        runtime_context: str | None = None,
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
        extra_settings = bot_settings.extra_settings if bot_settings else {}
        assistant_profile = (extra_settings or {}).get("assistant_profile") or {}
        training = assistant_profile.get("training") or {}
        response_length = training.get("response_length", "balanced")
        length_instruction = {
            "concise": "Yanıtı çoğunlukla 1-2 kısa cümlede tamamla.",
            "balanced": "Gerektiği kadar açık konuş; çoğunlukla 2-4 kısa cümle kullan.",
            "detailed": "Karmaşık sorularda ayrıntı ver ama tekrara ve gereksiz uzunluğa girme.",
        }.get(response_length, "Gerektiği kadar açık ve kısa konuş.")
        price_policy = training.get("price_policy", "known_only")
        price_instruction = {
            "known_only": "Fiyatı yalnızca doğrulanmış işletme bilgisinde varsa paylaş.",
            "confirm_before_sending": "Fiyat paylaşmadan önce müşterinin hangi hizmeti istediğini netleştir.",
            "never_share": "Fiyat paylaşma; güncel teklif için insan desteğine yönlendir.",
        }.get(price_policy, "Fiyat uydurma.")
        
        # Base prompt
        if custom_prompt:
            base_prompt = custom_prompt + "\n\n"
        else:
            base_prompt = f"""Bu görüşmede "{bot.name}" adına müşteri iletişimini yürüten asistansın.
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
4. {length_instruction}
5. Her zaman nazik ve yardımsever ol.
6. Dil: Türkçe (kullanıcı farklı dilde yazarsa o dilde cevap ver)
7. İnsan gibi doğal konuş; çağrı merkezi metni, reklam sloganı veya robotik kalıp kullanma.
8. "Merhaba" veya başka bir selamı yalnızca konuşmanın ilk yanıtında ve müşteri selam verdiyse kullan.
9. Her mesajda işletme adını, kendi adını veya "iletişime geçtiğiniz için teşekkürler" ifadesini tekrarlama.
10. Konuşma geçmişinde alınmış bir bilgiyi tekrar sorma; müşterinin son mesajına doğrudan cevap ver.
11. Aynı cümleyi veya soruyu art arda tekrarlama. Tek seferde en fazla bir net soru sor.
12. Kendinden "yapay zeka", "bot" veya "sistem" diye bahsetme; müşteri özellikle sorarsa dürüstçe dijital asistan olduğunu söyle.
13. {price_instruction}

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

        if runtime_context:
            base_prompt += f"\n{runtime_context.strip()}\n"
        
        return base_prompt

    @staticmethod
    def _remove_repeated_greeting(reply: str, messages: list[Message]) -> str:
        """Remove an unnecessary greeting after the assistant already joined the conversation."""
        if not any(message.sender == "bot" for message in messages):
            return reply.strip()
        cleaned = re.sub(
            r"^\s*(?:merhaba|selam(?:lar)?|iyi\s+(?:günler|akşamlar|sabahlar))"
            r"(?:\s+[^,\n.!?]{1,80})?\s*[,!.:-]?\s*",
            "",
            reply,
            count=1,
            flags=re.IGNORECASE,
        ).strip()
        return cleaned or reply.strip()
    
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
        bot_settings: Optional[BotSettings] = None,
        runtime_context: str | None = None,
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
        requested_max_tokens = settings_obj.max_response_length if bot_settings else 500
        max_tokens = max(100, min(requested_max_tokens, settings.AI_MAX_REPLY_TOKENS))
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
        system_prompt = self._build_system_prompt(
            bot,
            knowledge_items,
            bot_settings,
            runtime_context=runtime_context,
        )
        
        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation context with memory window
        if conversation.messages:
            context_messages = conversation.messages
            last_message = context_messages[-1]
            if last_message.sender != "bot" and last_message.content == last_user_message:
                context_messages = context_messages[:-1]
            context = self._build_conversation_context(context_messages, memory_window)
            messages.extend(context)
        
        # Add current user message
        messages.append({"role": "user", "content": last_user_message})
        
        try:
            response = await self._get_client().chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
            )
            
            reply = response.choices[0].message.content or fallback_msg
            reply = self._remove_repeated_greeting(reply, list(conversation.messages or []))
            
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
        
        except Exception:
            logger.exception("%s AI response generation failed", self.provider)
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
        
        except Exception:
            logger.exception("%s conversation summary generation failed", self.provider)
            return ""

    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_text: str,
        max_tokens: int = 1200,
        temperature: float = 0.3,
    ) -> str:
        """Run a provider-neutral, server-controlled text generation task."""
        response = await self._get_client().chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return (response.choices[0].message.content or "").strip()

    async def generate_voice_reply(
        self,
        *,
        bot: Bot,
        knowledge_items: list[BotKnowledgeItem],
        user_text: str,
        transcript: list[tuple[str, str]],
        bot_settings: Optional[BotSettings] = None,
        runtime_context: str | None = None,
    ) -> str:
        """Generate a short, tenant-aware reply suitable for text-to-speech."""
        system_prompt = self._build_system_prompt(
            bot,
            knowledge_items,
            bot_settings,
            runtime_context=runtime_context,
        )
        system_prompt += """

### SESLİ GÖRÜŞME KURALLARI
- Bu yanıt telefonda seslendirilecek; yalnızca doğal konuşma metni üret.
- Markdown, madde işareti, bağlantı, emoji veya teknik etiket kullanma.
- Çoğunlukla 1-2 kısa cümle kur ve aynı anda en fazla bir soru sor; uzun açıklamayı birkaç konuşma turuna böl.
- Her turda yeniden selamlama yapma.
- "Elbette", "memnuniyetle" ve "tabii ki" gibi kalıpları her yanıtta tekrarlama; müşterinin son sözüne doğrudan karşılık ver.
- Çağrı merkezi metni okur gibi konuşma. Günlük, sakin ve profesyonel Türkçe kullan; gereksiz resmiyet ve reklam cümlesi kurma.
- Müşterinin verdiği kısa onayları, isimleri ve tercihleri hatırla; aynı bilgiyi yeniden sorma.
- Cümlenin ortasında konu değiştirme. Önce soruyu yanıtla, gerekiyorsa ardından tek bir net soru sor.
- Yazım dilini Türkçe ses sentezine uygun tut; doğal duraklamalar için nokta ve virgül kullan.
- İngilizce veya teknik kısaltmaları telaffuz edilecek biçimde açık yaz; sembol, eğik çizgi ve parantez kullanma.
- Telefon numarası, tarih, saat, para ve ölçüleri konuşma dilinde kolay okunacak biçimde yaz.
- Gerçekte bir aktarım işlemi yapmadan "yetkiliye aktarıyorum" deme; yapamadığın işlemi yapmış gibi gösterme.
- Görüşmenin başında dijital asistan olduğu zaten belirtilir. Müşteri doğrudan sorarsa bunu dürüstçe doğrula; insan olduğunu iddia etme.
- GERÇEK RANDEVU BİLGİSİ mevcutsa randevu talebini yetkiliye aktarma; gerçek boş saatlerden en fazla üç seçenek sun.
- Müşteri önerdiğin saati açıkça onayladığında randevu işlem satırını eksiksiz üret. Bu görünmez işlem satırı doğal konuşma kuralının tek istisnasıdır.
- Bilmediğin fiyat, uygunluk veya işletme bilgisini uydurma.
"""
        messages = [{"role": "system", "content": system_prompt}]
        for speaker, text in transcript[-10:]:
            normalized = str(text or "").strip()
            if not normalized or normalized == user_text:
                continue
            messages.append({
                "role": "assistant" if speaker == "agent" else "user",
                "content": normalized[:2000],
            })
        messages.append({"role": "user", "content": user_text})
        try:
            response = await self._get_client().chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=140,
                temperature=0.65,
            )
            reply = (response.choices[0].message.content or "").strip()
            reply = re.sub(r"[*_`#]+", "", reply).strip()
            return reply or "Sizi dinliyorum. Biraz daha ayrıntı paylaşır mısınız?"
        except Exception:
            logger.exception("%s voice response generation failed", self.provider)
            return "Şu anda yanıt oluşturamıyorum. Lütfen daha sonra tekrar deneyin."


# Singleton instance
ai_service = AIService()
