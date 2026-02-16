"""
Real Estate Pack orchestration service (MVP).
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption import decrypt_token, encrypt_token
from app.models.bot import Bot
from app.models.conversation import Conversation
from app.models.feature_flag import FeatureFlag
from app.models.lead import Lead
from app.models.real_estate import (
    RealEstateAppointment,
    RealEstateConversationState,
    RealEstateFollowUpJob,
    RealEstateLeadListingEvent,
    RealEstateListing,
    RealEstatePackSettings,
    RealEstateTemplateRegistry,
    RealEstateWeeklyReport,
)
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.tenant_membership import TenantMembership
from app.models.user import User
from app.models.whatsapp_account import WhatsAppAccount
from app.services.email_service import EmailService
from app.services.google_calendar_service import GoogleCalendarError, GoogleCalendarService
from app.services.meta_api import meta_api_service
from app.services.pdf_service import SimplePdfService
from app.services.system_event_service import SystemEventService


DEFAULT_BUYER_FLOW = {
    "steps": [
        "sale_rent",
        "property_type",
        "location_text",
        "budget",
        "rooms",
        "timeline",
    ]
}

DEFAULT_SELLER_FLOW = {
    "steps": [
        "location_text",
        "property_type",
        "m2",
        "rooms",
        "building_age",
        "price_expectation",
        "urgency",
    ]
}

DEFAULT_LISTING_SOURCE = {
    "manual": True,
    "csv_import": True,
    "google_sheets": False,
    "remax_connector": False,
}

DEFAULT_TEMPLATE_DRAFTS = [
    {
        "name": "re_welcome_buyer",
        "category": "welcome",
        "content_preview": "Merhaba {{name}}, kriterlerinizi 1 dakikada netleştirip size en uygun 3 ilanı ileteyim.",
    },
    {
        "name": "re_welcome_seller",
        "category": "welcome",
        "content_preview": "Merhaba {{name}}, mülkünüzü 60 saniyede değerlendirme akışına alalım.",
    },
    {
        "name": "re_qualification_ping_1h",
        "category": "followup",
        "content_preview": "Kriterlerinizi tamamlayabilirsek sizin için en uygun seçenekleri hemen paylaşabilirim.",
    },
    {
        "name": "re_followup_recovery_1",
        "category": "followup",
        "content_preview": "Uygun olursanız size yeni çıkan ilanlardan kısa bir seçki paylaşabilirim.",
    },
    {
        "name": "re_followup_recovery_2",
        "category": "followup",
        "content_preview": "Sizin için güncellediğim portföy listesini tekrar iletmemi ister misiniz?",
    },
    {
        "name": "re_appointment_confirmation",
        "category": "appointment",
        "content_preview": "Randevunuz {{date}} {{time}} için oluşturuldu. Görüşme detaylarını paylaşıyorum.",
    },
    {
        "name": "re_appointment_reminder_1h",
        "category": "appointment",
        "content_preview": "Randevunuza 1 saat kaldı. Konum ve hazırlık notları aşağıdadır.",
    },
    {
        "name": "re_listing_suggestions",
        "category": "listing",
        "content_preview": "Kriterlerinize göre öne çıkan 3 ilanı sizin için derledim.",
    },
    {
        "name": "re_seller_intake_summary",
        "category": "seller",
        "content_preview": "Mülkünüz için ön değerlendirme tamamlandı. Özet rapor danışmanınıza iletildi.",
    },
    {
        "name": "re_optout_ack",
        "category": "compliance",
        "content_preview": "Takip mesajlarını durdurdum. Yeniden başlatmak için 'Başlat' yazabilirsiniz.",
    },
]


PERSONA_INTRO = {
    "luxury": "Özel portföyünüz için seçtiğim öne çıkan seçenekler:",
    "pro": "Kriterlerinize göre uygun olabilecek seçenekler:",
    "warm": "Size uygun olabilecek ilanları özenle seçtim:",
}


@dataclass
class RealEstateMessageResult:
    handled: bool
    response_text: str | None = None


class RealEstateService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_settings(self, tenant_id: UUID) -> RealEstatePackSettings:
        settings = self.db.query(RealEstatePackSettings).filter(
            RealEstatePackSettings.tenant_id == tenant_id
        ).first()
        if settings:
            return settings

        settings = RealEstatePackSettings(
            tenant_id=tenant_id,
            enabled=False,
            persona="pro",
            question_flow_buyer=DEFAULT_BUYER_FLOW,
            question_flow_seller=DEFAULT_SELLER_FLOW,
            listings_source=DEFAULT_LISTING_SOURCE,
        )
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        self.ensure_default_templates(tenant_id)
        return settings

    def ensure_default_templates(self, tenant_id: UUID) -> None:
        existing_count = self.db.query(RealEstateTemplateRegistry).filter(
            RealEstateTemplateRegistry.tenant_id == tenant_id
        ).count()
        if existing_count > 0:
            return

        for draft in DEFAULT_TEMPLATE_DRAFTS:
            self.db.add(
                RealEstateTemplateRegistry(
                    tenant_id=tenant_id,
                    name=draft["name"],
                    category=draft["category"],
                    language="tr",
                    status="draft",
                    variables_schema={},
                    content_preview=draft["content_preview"],
                    is_approved=False,
                )
            )
        self.db.commit()

    def upsert_settings(self, tenant_id: UUID, payload: dict[str, Any]) -> RealEstatePackSettings:
        settings = self.get_or_create_settings(tenant_id)
        for key, value in payload.items():
            if hasattr(settings, key) and value is not None:
                setattr(settings, key, value)
        self.db.commit()
        self.db.refresh(settings)
        self.ensure_pack_feature_flag(tenant_id, settings.enabled)
        self.ensure_default_templates(tenant_id)
        return settings

    def ensure_pack_feature_flag(self, tenant_id: UUID, enabled: bool) -> None:
        feature = self.db.query(FeatureFlag).filter(
            FeatureFlag.tenant_id == tenant_id,
            FeatureFlag.key == "real_estate_pack",
        ).first()
        if feature:
            feature.enabled = enabled
        else:
            self.db.add(
                FeatureFlag(
                    tenant_id=tenant_id,
                    key="real_estate_pack",
                    enabled=enabled,
                    payload_json=None,
                )
            )
        self.db.commit()

    def is_pack_enabled(self, tenant_id: UUID) -> bool:
        settings = self.get_or_create_settings(tenant_id)
        if settings.enabled:
            return True
        feature = self.db.query(FeatureFlag).filter(
            FeatureFlag.tenant_id == tenant_id,
            FeatureFlag.key == "real_estate_pack",
            FeatureFlag.enabled.is_(True),
        ).first()
        return feature is not None

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        if not phone:
            return phone
        raw = re.sub(r"[^\d+]", "", phone.strip())
        if raw.startswith("00"):
            raw = f"+{raw[2:]}"
        if raw and not raw.startswith("+"):
            raw = f"+{raw}"
        return raw

    @staticmethod
    def _extract_price_token(token: str, suffix: str | None) -> int | None:
        try:
            normalized = token.replace(".", "").replace(",", ".")
            base = float(normalized)
        except ValueError:
            return None

        suffix_norm = (suffix or "").lower().strip()
        if suffix_norm in {"m", "mn", "milyon"}:
            return int(base * 1_000_000)
        if suffix_norm in {"k", "bin"}:
            return int(base * 1_000)
        return int(base)

    def _parse_budget_range(self, text_lower: str) -> tuple[int | None, int | None]:
        range_match = re.search(
            r"(\d+(?:[.,]\d+)?)\s*(milyon|m|bin|k)?\s*[-–]\s*(\d+(?:[.,]\d+)?)\s*(milyon|m|bin|k)?",
            text_lower,
        )
        if range_match:
            min_budget = self._extract_price_token(range_match.group(1), range_match.group(2))
            max_budget = self._extract_price_token(range_match.group(3), range_match.group(4))
            return min_budget, max_budget

        candidates = re.findall(r"(\d+(?:[.,]\d+)?)\s*(milyon|m|bin|k)?", text_lower)
        parsed = []
        for raw_token, suffix in candidates:
            price = self._extract_price_token(raw_token, suffix)
            if price and 50_000 <= price <= 1_000_000_000:
                parsed.append(price)

        if not parsed:
            return None, None
        if len(parsed) == 1:
            return None, parsed[0]

        parsed.sort()
        return parsed[0], parsed[-1]

    def parse_message(self, text: str) -> dict[str, Any]:
        lowered = (text or "").strip().lower()
        parsed: dict[str, Any] = {
            "intent": None,
            "sale_rent": None,
            "property_type": None,
            "location_text": None,
            "budget_min": None,
            "budget_max": None,
            "rooms": None,
            "m2_min": None,
            "timeline_text": None,
            "mortgage_required": None,
            "wants_appointment": False,
            "opt_out": False,
            "handoff_signal": False,
        }

        stop_keywords = {"durdur", "stop", "iptal", "abonelikten çık", "vazgeç"}
        if any(keyword in lowered for keyword in stop_keywords):
            parsed["opt_out"] = True
            return parsed

        seller_keywords = {
            "satmak istiyorum",
            "evimi sat",
            "evimi satmak",
            "kiraya vermek",
            "satıcıyım",
            "mülkümü sat",
        }
        buyer_keywords = {
            "ev bak",
            "ev arıyorum",
            "ev almak",
            "satılık",
            "kiralık",
            "daire arıyorum",
        }

        if any(keyword in lowered for keyword in seller_keywords):
            parsed["intent"] = "seller"
        elif any(keyword in lowered for keyword in buyer_keywords):
            parsed["intent"] = "buyer"

        if "kiralık" in lowered:
            parsed["sale_rent"] = "rent"
        elif "satılık" in lowered:
            parsed["sale_rent"] = "sale"

        property_types = {
            "daire": "daire",
            "villa": "villa",
            "arsa": "arsa",
            "ofis": "ofis",
            "dükkan": "dukkan",
            "işyeri": "isyeri",
            "müstakil": "mustakil",
        }
        for key, value in property_types.items():
            if key in lowered:
                parsed["property_type"] = value
                break

        location_keywords = [
            "ankara",
            "istanbul",
            "izmir",
            "antalya",
            "bursa",
            "çankaya",
            "keçiören",
            "yenimahalle",
            "etimesgut",
            "mamak",
            "sincan",
            "kadıköy",
            "beşiktaş",
            "üsküdar",
            "bornova",
            "konak",
        ]
        found_locations = [loc for loc in location_keywords if loc in lowered]
        if found_locations:
            parsed["location_text"] = ", ".join(dict.fromkeys(found_locations[:2])).title()

        budget_min, budget_max = self._parse_budget_range(lowered)
        parsed["budget_min"] = budget_min
        parsed["budget_max"] = budget_max

        rooms_match = re.search(r"(\d)\s*\+\s*(\d)", lowered)
        if rooms_match:
            parsed["rooms"] = f"{rooms_match.group(1)}+{rooms_match.group(2)}"
        else:
            room_text = re.search(r"(\d{1,2})\s*oda", lowered)
            if room_text:
                parsed["rooms"] = room_text.group(1)

        m2_match = re.search(r"(\d{2,4})\s*m2", lowered)
        if m2_match:
            parsed["m2_min"] = int(m2_match.group(1))

        timeline_keywords = {
            "hemen": "hemen",
            "acil": "acil",
            "1 ay": "1 ay",
            "2 ay": "2 ay",
            "3 ay": "3 ay",
            "6 ay": "6 ay",
        }
        for key, value in timeline_keywords.items():
            if key in lowered:
                parsed["timeline_text"] = value
                break

        if "kredi" in lowered:
            parsed["mortgage_required"] = True

        if any(keyword in lowered for keyword in {"randevu", "gösterim", "yerinde görmek", "görüşme"}):
            parsed["wants_appointment"] = True

        if any(keyword in lowered for keyword in {"insan", "danışman", "yetkili", "telefonla konuş"}):
            parsed["handoff_signal"] = True

        return parsed

    def _upsert_lead(self, tenant_id: UUID, bot: Bot, conversation: Conversation, phone: str, contact_name: str | None) -> Lead:
        normalized_phone = self._normalize_phone(phone)
        lead = None
        if conversation.lead and conversation.lead.tenant_id == tenant_id:
            lead = conversation.lead
        if lead is None:
            lead = self.db.query(Lead).filter(
                Lead.tenant_id == tenant_id,
                Lead.phone == normalized_phone,
                Lead.is_deleted.is_(False),
            ).order_by(Lead.created_at.desc()).first()

        if lead is None:
            lead = Lead(
                tenant_id=tenant_id,
                bot_id=bot.id,
                conversation_id=conversation.id,
                name=contact_name,
                phone=normalized_phone,
                source="whatsapp",
                status="new",
                is_auto_detected=True,
                detected_fields={},
                tags=["real_estate_pack"],
                extra_data={},
            )
            self.db.add(lead)
            self.db.flush()
        else:
            lead.bot_id = bot.id
            lead.conversation_id = conversation.id
            if contact_name and not lead.name:
                lead.name = contact_name
            if normalized_phone and not lead.phone:
                lead.phone = normalized_phone
            lead.updated_at = datetime.utcnow()

        conversation.lead = lead
        conversation.has_lead = True
        return lead

    def _get_or_create_state(
        self,
        tenant_id: UUID,
        conversation: Conversation,
        lead: Lead,
        contact_name: str | None,
        phone: str,
    ) -> RealEstateConversationState:
        state = self.db.query(RealEstateConversationState).filter(
            RealEstateConversationState.conversation_id == conversation.id
        ).first()
        if state:
            return state

        pii_payload = {
            "name": contact_name,
            "phone": self._normalize_phone(phone),
        }
        state = RealEstateConversationState(
            tenant_id=tenant_id,
            conversation_id=conversation.id,
            lead_id=lead.id,
            current_state="welcome",
            intent="unknown",
            confidence=0.0,
            collected_data={},
            pii_snapshot_encrypted=encrypt_token(json.dumps(pii_payload, ensure_ascii=False)),
            window_open_until=datetime.utcnow() + timedelta(hours=24),
        )
        self.db.add(state)
        self.db.flush()
        return state

    @staticmethod
    def _is_data_ready_for_listing_match(data: dict[str, Any]) -> bool:
        required = ["sale_rent", "property_type", "location_text", "budget_max"]
        return all(data.get(field) for field in required)

    def _next_buyer_question(self, data: dict[str, Any]) -> str | None:
        if not data.get("sale_rent"):
            return "Satılık mı kiralık mı arıyorsunuz?"
        if not data.get("property_type"):
            return "Hangi mülk tipi öncelikli: daire, villa, arsa veya ofis?"
        if not data.get("location_text"):
            return "Öncelikli lokasyon/bölgeyi paylaşır mısınız?"
        if not data.get("budget_max"):
            return "Bütçe aralığınızı paylaşır mısınız? (Örn: 3-4 milyon)"
        if not data.get("rooms"):
            return "Kaç oda tercih ediyorsunuz? (Örn: 3+1)"
        return None

    def _next_seller_question(self, data: dict[str, Any]) -> str | None:
        if not data.get("location_text"):
            return "Mülkünüz hangi bölgede bulunuyor?"
        if not data.get("property_type"):
            return "Mülkünüzün tipi nedir? (daire/villa/arsa/ofis)"
        if not data.get("m2_min"):
            return "Yaklaşık brüt m² bilgisini paylaşır mısınız?"
        if not data.get("rooms"):
            return "Oda planı nedir? (Örn: 3+1)"
        if not data.get("budget_max"):
            return "Fiyat beklentinizi paylaşır mısınız?"
        return None

    def _build_seller_summary(self, lead: Lead, state: RealEstateConversationState) -> str:
        data = state.collected_data or {}
        summary = {
            "intent": state.intent,
            "property_type": data.get("property_type"),
            "location_text": data.get("location_text"),
            "m2": data.get("m2_min"),
            "rooms": data.get("rooms"),
            "price_expectation": data.get("budget_max"),
            "timeline": data.get("timeline_text"),
        }
        lead.status = "qualified"
        lead.tags = list(set([*(lead.tags or []), "seller", "handoff_agent"]))
        lead.extra_data = {
            **(lead.extra_data or {}),
            "real_estate_seller_summary": summary,
            "seller_service_report_due": True,
        }
        return (
            "Satıcı ön değerlendirme tamamlandı ✅\n"
            "Danışmanımıza özet rapor iletildi. "
            "En kısa sürede sizinle iletişime geçeceğiz."
        )

    def _build_listing_message(self, settings: RealEstatePackSettings, listings: list[RealEstateListing]) -> str:
        intro = PERSONA_INTRO.get((settings.persona or "pro").lower(), PERSONA_INTRO["pro"])
        lines = [intro]
        for idx, listing in enumerate(listings, start=1):
            line = (
                f"{idx}) {listing.title} • {listing.location_text} • "
                f"{listing.price:,} {listing.currency}"
            )
            if listing.rooms:
                line += f" • {listing.rooms}"
            if listing.m2:
                line += f" • {listing.m2} m²"
            if listing.url:
                line += f"\n{listing.url}"
            lines.append(line)
        lines.append("Uygun görürseniz randevu için gün/saat paylaşabilirsiniz.")
        return "\n\n".join(lines)

    def suggest_listings(
        self,
        tenant_id: UUID,
        criteria: dict[str, Any],
        limit: int = 3,
        lead_id: UUID | None = None,
    ) -> list[RealEstateListing]:
        query = self.db.query(RealEstateListing).filter(
            RealEstateListing.tenant_id == tenant_id,
            RealEstateListing.is_active.is_(True),
        )

        sale_rent = criteria.get("sale_rent")
        if sale_rent:
            query = query.filter(RealEstateListing.sale_rent == sale_rent)

        property_type = criteria.get("property_type")
        if property_type:
            query = query.filter(RealEstateListing.property_type == property_type)

        location_text = criteria.get("location_text")

        budget_min = criteria.get("budget_min")
        budget_max = criteria.get("budget_max")
        if budget_min:
            query = query.filter(RealEstateListing.price >= int(budget_min * 0.85))
        if budget_max:
            query = query.filter(RealEstateListing.price <= int(budget_max * 1.20))

        candidates = query.order_by(RealEstateListing.created_at.desc()).limit(200).all()
        if not candidates:
            return []

        target_budget = budget_max or budget_min or 0
        target_rooms = criteria.get("rooms")
        target_m2 = criteria.get("m2_min")
        location_tokens = [
            token.strip().lower()
            for token in re.split(r"[,\s]+", (location_text or "").strip())
            if token.strip()
        ]

        lead_event_boost: dict[UUID, float] = {}
        preferred_types: set[str] = set()
        preferred_location_tokens: set[str] = set()
        if lead_id:
            lead_history = self.db.query(RealEstateLeadListingEvent).filter(
                RealEstateLeadListingEvent.tenant_id == tenant_id,
                RealEstateLeadListingEvent.lead_id == lead_id,
                RealEstateLeadListingEvent.event.in_(["clicked", "saved", "ignored"]),
            ).all()
            for event in lead_history:
                if not event.listing_id:
                    continue
                if event.event == "saved":
                    lead_event_boost[event.listing_id] = lead_event_boost.get(event.listing_id, 0.0) + 2.4
                elif event.event == "clicked":
                    lead_event_boost[event.listing_id] = lead_event_boost.get(event.listing_id, 0.0) + 1.6
                elif event.event == "ignored":
                    lead_event_boost[event.listing_id] = lead_event_boost.get(event.listing_id, 0.0) - 1.2

            if lead_history:
                clicked_listing_ids = [row.listing_id for row in lead_history if row.listing_id]
                historical_listings = self.db.query(RealEstateListing).filter(
                    RealEstateListing.tenant_id == tenant_id,
                    RealEstateListing.id.in_(clicked_listing_ids),
                ).all()
                for item in historical_listings:
                    if item.property_type:
                        preferred_types.add(item.property_type)
                    for token in re.split(r"[,\s]+", (item.location_text or "").lower()):
                        token = token.strip()
                        if len(token) >= 3:
                            preferred_location_tokens.add(token)

        popularity_rows = self.db.query(
            RealEstateLeadListingEvent.listing_id,
            func.count(RealEstateLeadListingEvent.id),
        ).filter(
            RealEstateLeadListingEvent.tenant_id == tenant_id,
            RealEstateLeadListingEvent.listing_id.isnot(None),
            RealEstateLeadListingEvent.event.in_(["clicked", "saved"]),
            RealEstateLeadListingEvent.created_at >= datetime.utcnow() - timedelta(days=120),
        ).group_by(RealEstateLeadListingEvent.listing_id).all()
        popularity_map = {listing_id: int(count) for listing_id, count in popularity_rows if listing_id}
        max_popularity = max(popularity_map.values(), default=1)

        scored: list[tuple[float, RealEstateListing]] = []
        for listing in candidates:
            score = 0.0
            listing_location = (listing.location_text or "").lower()
            if location_tokens:
                token_hits = sum(1 for token in location_tokens if token in listing_location)
                score += min(3.5, token_hits * 1.5)
            if property_type and listing.property_type == property_type:
                score += 2.0
            if sale_rent and listing.sale_rent == sale_rent:
                score += 1.5

            if target_budget > 0:
                price_diff_ratio = abs(listing.price - target_budget) / max(target_budget, 1)
                score += max(0, 3.0 - (price_diff_ratio * 3.0))

            if target_rooms and listing.rooms and listing.rooms == target_rooms:
                score += 1.2

            if target_m2 and listing.m2:
                m2_diff_ratio = abs(listing.m2 - target_m2) / max(target_m2, 1)
                score += max(0, 1.2 - (m2_diff_ratio * 1.2))

            score += lead_event_boost.get(listing.id, 0.0)

            if preferred_types and listing.property_type in preferred_types:
                score += 0.8

            if preferred_location_tokens:
                if any(token in listing_location for token in preferred_location_tokens):
                    score += 0.8

            popularity = popularity_map.get(listing.id, 0)
            if popularity > 0:
                score += min(1.6, (popularity / max_popularity) * 1.6)

            scored.append((score, listing))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [listing for _, listing in scored[:limit]]

    def _record_listing_sent_events(self, tenant_id: UUID, lead_id: UUID, listings: list[RealEstateListing]) -> None:
        for listing in listings:
            self.db.add(
                RealEstateLeadListingEvent(
                    tenant_id=tenant_id,
                    lead_id=lead_id,
                    listing_id=listing.id,
                    event="sent",
                    meta_json={"source": "auto_matcher"},
                )
            )

    def _schedule_followup(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        conversation_id: UUID,
        message_text: str,
        attempt_no: int,
        max_attempts: int,
        delay: timedelta,
    ) -> None:
        existing = self.db.query(RealEstateFollowUpJob).filter(
            RealEstateFollowUpJob.tenant_id == tenant_id,
            RealEstateFollowUpJob.lead_id == lead_id,
            RealEstateFollowUpJob.conversation_id == conversation_id,
            RealEstateFollowUpJob.attempt_no == attempt_no,
            RealEstateFollowUpJob.status == "pending",
        ).first()
        if existing:
            return

        self.db.add(
            RealEstateFollowUpJob(
                tenant_id=tenant_id,
                lead_id=lead_id,
                conversation_id=conversation_id,
                scheduled_at=datetime.utcnow() + delay,
                attempt_no=attempt_no,
                max_attempts=max_attempts,
                status="pending",
                message_text=message_text,
            )
        )

    def _build_qualification_response(
        self,
        lead: Lead,
        state: RealEstateConversationState,
        settings: RealEstatePackSettings,
        parsed: dict[str, Any],
    ) -> str:
        data = state.collected_data or {}

        if parsed.get("handoff_signal"):
            state.current_state = "handoff_agent"
            lead.status = "contacted"
            lead.tags = list(set([*(lead.tags or []), "handoff_agent"]))
            return "Sizi danışmanımıza bağlıyorum. Kısa süre içinde sizinle iletişime geçecek."

        if state.intent == "seller":
            next_question = self._next_seller_question(data)
            if next_question:
                state.current_state = "qualify"
                return next_question
            state.current_state = "handoff_agent"
            return self._build_seller_summary(lead, state)

        if parsed.get("wants_appointment") and self._is_data_ready_for_listing_match(data):
            state.current_state = "appointment"
            lead.status = "contacted"
            return "Randevu planlayalım. Uygun olduğunuz gün ve saat aralığını paylaşır mısınız?"

        if self._is_data_ready_for_listing_match(data):
            matches = self.suggest_listings(lead.tenant_id, data, limit=3, lead_id=lead.id)
            if matches:
                state.current_state = "match_listings"
                lead.status = "qualified"
                self._record_listing_sent_events(lead.tenant_id, lead.id, matches)
                return self._build_listing_message(settings, matches)

            state.current_state = "qualify"
            return "Bu kriterlere tam uyan ilan bulamadım. Bölge veya bütçeyi biraz esnetmek ister misiniz?"

        next_question = self._next_buyer_question(data)
        state.current_state = "qualify"
        return next_question or "Kriterlerinizi biraz daha netleştirebilirsem en doğru ilanları önerebilirim."

    def handle_inbound_whatsapp_message(
        self,
        *,
        tenant_id: UUID,
        bot: Bot,
        conversation: Conversation,
        from_number: str,
        contact_name: str | None,
        text: str,
    ) -> RealEstateMessageResult:
        if not self.is_pack_enabled(tenant_id):
            return RealEstateMessageResult(handled=False)

        settings = self.get_or_create_settings(tenant_id)
        self.ensure_default_templates(tenant_id)

        parsed = self.parse_message(text)
        lead = self._upsert_lead(tenant_id, bot, conversation, from_number, contact_name)
        state = self._get_or_create_state(tenant_id, conversation, lead, contact_name, from_number)

        now = datetime.utcnow()
        state.window_open_until = now + timedelta(hours=24)
        state.last_customer_message_at = now

        if parsed.get("opt_out"):
            state.opted_out = True
            state.current_state = "followup"
            lead.status = "lost"
            lead.tags = list(set([*(lead.tags or []), "opt_out"]))
            self.db.commit()
            return RealEstateMessageResult(
                handled=True,
                response_text="Takibi durdurdum. Yeniden başlatmak için \"Başlat\" yazabilirsiniz.",
            )

        if state.opted_out:
            return RealEstateMessageResult(handled=True, response_text=None)

        data = dict(state.collected_data or {})
        for key in [
            "sale_rent",
            "property_type",
            "location_text",
            "budget_min",
            "budget_max",
            "rooms",
            "m2_min",
            "timeline_text",
            "mortgage_required",
        ]:
            if parsed.get(key) is not None:
                data[key] = parsed[key]
        state.collected_data = data

        if parsed.get("intent"):
            state.intent = parsed["intent"]
            lead.extra_data = {
                **(lead.extra_data or {}),
                "real_estate_intent": parsed["intent"],
            }
            lead.tags = list(set([*(lead.tags or []), parsed["intent"]]))

        if state.intent == "unknown":
            state.current_state = "welcome"
            response = "Merhaba 👋 Ev alma mı, satma mı planlıyorsunuz? Size 1 dakikada en uygun akışı başlatayım."
        else:
            response = self._build_qualification_response(lead, state, settings, parsed)

        if response:
            state.last_outbound_message_at = now
            self._schedule_followup(
                tenant_id=tenant_id,
                lead_id=lead.id,
                conversation_id=conversation.id,
                message_text="Kriterlerinizi tamamlamanız halinde en uygun seçenekleri hemen paylaşabilirim.",
                attempt_no=1,
                max_attempts=max(settings.followup_attempts, 1),
                delay=timedelta(hours=1),
            )

        SystemEventService(self.db).log(
            tenant_id=str(tenant_id),
            source="real_estate_pack",
            level="info",
            code="RE_STATE_TRANSITION",
            message=f"state={state.current_state}, intent={state.intent}",
            meta_json={
                "conversation_id": str(conversation.id),
                "lead_id": str(lead.id),
                "state": state.current_state,
                "intent": state.intent,
            },
        )

        self.db.commit()
        return RealEstateMessageResult(handled=True, response_text=response)

    async def run_followups(self, tenant_id: UUID) -> dict[str, int]:
        now = datetime.utcnow()
        settings = self.get_or_create_settings(tenant_id)
        if not settings.enabled:
            return {"pending": 0, "sent": 0, "skipped": 0, "failed": 0}

        jobs = self.db.query(RealEstateFollowUpJob).filter(
            RealEstateFollowUpJob.tenant_id == tenant_id,
            RealEstateFollowUpJob.status == "pending",
            RealEstateFollowUpJob.scheduled_at <= now,
        ).order_by(RealEstateFollowUpJob.scheduled_at.asc()).all()

        pending = len(jobs)
        sent = 0
        skipped = 0
        failed = 0

        account = self.db.query(WhatsAppAccount).filter(
            WhatsAppAccount.tenant_id == tenant_id,
            WhatsAppAccount.is_active.is_(True),
        ).first()
        access_token = decrypt_token(account.access_token_encrypted) if account else None

        for job in jobs:
            state = self.db.query(RealEstateConversationState).filter(
                RealEstateConversationState.conversation_id == job.conversation_id
            ).first()
            lead = self.db.query(Lead).filter(Lead.id == job.lead_id).first()
            conversation = self.db.query(Conversation).filter(Conversation.id == job.conversation_id).first()

            if not lead or not conversation or (state and state.opted_out):
                job.status = "skipped"
                job.error_text = "lead_or_conversation_missing_or_opted_out"
                skipped += 1
                continue

            if state and state.last_customer_message_at and state.last_customer_message_at > job.created_at:
                job.status = "skipped"
                job.error_text = "customer_replied_after_schedule"
                skipped += 1
                continue

            if not account or not access_token:
                job.status = "failed"
                job.error_text = "whatsapp_account_missing"
                failed += 1
                continue

            outbound_text = job.message_text or "Uygun olursanız kısa bir güncelleme paylaşabilirim."
            try:
                use_template = bool(state and state.window_open_until and now > state.window_open_until)
                if use_template:
                    template = self.db.query(RealEstateTemplateRegistry).filter(
                        RealEstateTemplateRegistry.tenant_id == tenant_id,
                        RealEstateTemplateRegistry.category == "followup",
                        RealEstateTemplateRegistry.is_approved.is_(True),
                        RealEstateTemplateRegistry.meta_template_id.isnot(None),
                    ).order_by(RealEstateTemplateRegistry.updated_at.desc()).first()
                    if template:
                        await meta_api_service.send_template_message(
                            access_token=access_token,
                            phone_number_id=account.phone_number_id,
                            to=conversation.external_user_id,
                            template_name=template.meta_template_id,
                            language_code=template.language or "tr",
                        )
                    else:
                        await meta_api_service.send_text_message(
                            access_token=access_token,
                            phone_number_id=account.phone_number_id,
                            to=conversation.external_user_id,
                            text=outbound_text,
                        )
                else:
                    await meta_api_service.send_text_message(
                        access_token=access_token,
                        phone_number_id=account.phone_number_id,
                        to=conversation.external_user_id,
                        text=outbound_text,
                    )

                job.status = "sent"
                job.sent_at = now
                sent += 1

                if job.attempt_no < job.max_attempts:
                    next_delay = timedelta(days=1 if job.attempt_no == 1 else settings.followup_days)
                    self._schedule_followup(
                        tenant_id=tenant_id,
                        lead_id=job.lead_id,
                        conversation_id=job.conversation_id,
                        message_text=outbound_text,
                        attempt_no=job.attempt_no + 1,
                        max_attempts=job.max_attempts,
                        delay=next_delay,
                    )

            except Exception as exc:
                job.status = "failed"
                job.error_text = str(exc)[:500]
                failed += 1

        self.db.commit()
        return {"pending": pending, "sent": sent, "skipped": skipped, "failed": failed}

    def book_appointment(
        self,
        *,
        tenant_id: UUID,
        lead_id: UUID,
        agent_id: UUID | None,
        start_at: datetime,
        end_at: datetime,
        listing_id: UUID | None = None,
        meeting_mode: str = "in_person",
        notes: str | None = None,
    ) -> RealEstateAppointment:
        settings = self.get_or_create_settings(tenant_id)
        lead = self.db.query(Lead).filter(
            Lead.id == lead_id,
            Lead.tenant_id == tenant_id,
        ).first()

        appointment = RealEstateAppointment(
            tenant_id=tenant_id,
            lead_id=lead_id,
            agent_id=agent_id,
            listing_id=listing_id,
            start_at=start_at,
            end_at=end_at,
            status="scheduled",
            meeting_mode=meeting_mode,
            notes=notes,
            calendar_provider="manual",
        )
        self.db.add(appointment)

        if settings.google_calendar_enabled and agent_id:
            try:
                gc_service = GoogleCalendarService(self.db)
                if gc_service.is_configured():
                    event_id = gc_service.create_event(
                        tenant_id=tenant_id,
                        agent_id=agent_id,
                        summary=f"SvontAI Randevu • {lead.name if lead and lead.name else 'Müşteri'}",
                        description=notes or "Real Estate Pack randevusu",
                        start_at=start_at,
                        end_at=end_at,
                        attendee_email=lead.email if lead else None,
                    )
                    appointment.calendar_provider = "google"
                    appointment.calendar_event_id = event_id
            except GoogleCalendarError as exc:
                SystemEventService(self.db).log(
                    tenant_id=str(tenant_id),
                    source="real_estate_pack",
                    level="warn",
                    code="RE_GOOGLE_CALENDAR_EVENT_FAILED",
                    message=str(exc)[:500],
                    meta_json={"lead_id": str(lead_id), "agent_id": str(agent_id)},
                )

        self.db.commit()
        self.db.refresh(appointment)
        return appointment

    def suggest_listings_for_lead(self, tenant_id: UUID, lead_id: UUID) -> list[RealEstateListing]:
        state = self.db.query(RealEstateConversationState).filter(
            RealEstateConversationState.tenant_id == tenant_id,
            RealEstateConversationState.lead_id == lead_id,
        ).first()
        if not state:
            return []

        matches = self.suggest_listings(
            tenant_id,
            state.collected_data or {},
            limit=3,
            lead_id=lead_id,
        )
        if matches:
            self._record_listing_sent_events(tenant_id, lead_id, matches)
            self.db.commit()
        return matches

    def suggest_listings_with_reasons(self, tenant_id: UUID, lead_id: UUID, limit: int = 3) -> list[dict[str, Any]]:
        state = self.db.query(RealEstateConversationState).filter(
            RealEstateConversationState.tenant_id == tenant_id,
            RealEstateConversationState.lead_id == lead_id,
        ).first()
        if not state:
            return []

        criteria = state.collected_data or {}
        listings = self.suggest_listings(tenant_id, criteria, limit=limit, lead_id=lead_id)
        location_text = (criteria.get("location_text") or "").lower()
        budget_max = criteria.get("budget_max")
        property_type = criteria.get("property_type")

        output: list[dict[str, Any]] = []
        for item in listings:
            reasons: list[str] = []
            if property_type and item.property_type == property_type:
                reasons.append("Mülk tipi tercihinizle uyumlu")
            if location_text and location_text.split(" ")[0] in (item.location_text or "").lower():
                reasons.append("Bölge tercihine yakın")
            if budget_max and item.price <= int(budget_max * 1.15):
                reasons.append("Bütçe bandına yakın")

            interaction_count = self.db.query(func.count(RealEstateLeadListingEvent.id)).filter(
                RealEstateLeadListingEvent.tenant_id == tenant_id,
                RealEstateLeadListingEvent.lead_id == lead_id,
                RealEstateLeadListingEvent.listing_id == item.id,
                RealEstateLeadListingEvent.event.in_(["clicked", "saved"]),
            ).scalar() or 0
            if interaction_count > 0:
                reasons.append("Geçmiş etkileşim sinyali güçlü")

            output.append(
                {
                    "listing": item,
                    "reasons": reasons or ["Kriterlerinizle genel uyum yüksek"],
                }
            )
        return output

    def record_listing_event(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        listing_id: UUID,
        event: str,
        meta_json: dict[str, Any] | None = None,
    ) -> RealEstateLeadListingEvent:
        row = RealEstateLeadListingEvent(
            tenant_id=tenant_id,
            lead_id=lead_id,
            listing_id=listing_id,
            event=event,
            meta_json=meta_json or {},
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def _price_analysis_text(
        self,
        *,
        listing: RealEstateListing,
        comparable_prices: list[int],
    ) -> tuple[str, float | None, float | None]:
        if not comparable_prices:
            return "Karşılaştırma için yeterli veri yok.", None, None

        avg_price = statistics.mean(comparable_prices)
        median_price = statistics.median(comparable_prices)
        if median_price <= 0:
            return "Karşılaştırma için yeterli veri yok.", avg_price, median_price

        ratio = listing.price / median_price
        if ratio < 0.95:
            note = "Portföy medyanına göre daha rekabetçi fiyat."
        elif ratio > 1.08:
            note = "Portföy medyanına göre premium fiyat segmentinde."
        else:
            note = "Portföy medyanına yakın dengeli fiyat."
        return note, avg_price, median_price

    def build_listing_summary(
        self,
        tenant_id: UUID,
        listing_ids: list[UUID],
        lead_id: UUID | None = None,
    ) -> dict[str, Any]:
        rows = self.db.query(RealEstateListing).filter(
            RealEstateListing.tenant_id == tenant_id,
            RealEstateListing.id.in_(listing_ids),
        ).all()
        if not rows:
            return {"generated_at": datetime.utcnow().isoformat(), "items": []}

        lead = None
        if lead_id:
            lead = self.db.query(Lead).filter(
                Lead.id == lead_id,
                Lead.tenant_id == tenant_id,
            ).first()

        items: list[dict[str, Any]] = []
        for listing in rows:
            comparable_prices = [
                int(value[0])
                for value in self.db.query(RealEstateListing.price).filter(
                    RealEstateListing.tenant_id == tenant_id,
                    RealEstateListing.is_active.is_(True),
                    RealEstateListing.sale_rent == listing.sale_rent,
                    RealEstateListing.property_type == listing.property_type,
                    RealEstateListing.price.isnot(None),
                ).limit(400).all()
            ]
            price_note, avg_price, median_price = self._price_analysis_text(
                listing=listing,
                comparable_prices=comparable_prices,
            )
            location_note = ""
            if isinstance(listing.features, dict):
                location_note = (
                    listing.features.get("location_note")
                    or listing.features.get("social_note")
                    or ""
                )
            if not location_note:
                location_note = "Lokasyon notu girilmemiş."

            reason = "Kriterlerle uyumlu seçenek"
            if lead and isinstance(lead.extra_data, dict):
                reason = lead.extra_data.get("real_estate_intent") == "buyer" and "Alıcı kriterlerine yakın seçenek" or reason

            items.append(
                {
                    "listing_id": str(listing.id),
                    "title": listing.title,
                    "sale_rent": listing.sale_rent,
                    "property_type": listing.property_type,
                    "location_text": listing.location_text,
                    "price": listing.price,
                    "currency": listing.currency,
                    "rooms": listing.rooms,
                    "m2": listing.m2,
                    "url": listing.url,
                    "price_analysis_note": price_note,
                    "portfolio_avg_price": avg_price,
                    "portfolio_median_price": median_price,
                    "location_note": location_note,
                    "reason": reason,
                }
            )

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "lead_id": str(lead_id) if lead_id else None,
            "items": items,
        }

    def generate_listing_summary_pdf(
        self,
        tenant_id: UUID,
        listing_ids: list[UUID],
        lead_id: UUID | None = None,
    ) -> tuple[dict[str, Any], bytes, str]:
        summary = self.build_listing_summary(tenant_id, listing_ids, lead_id=lead_id)
        rows = summary.get("items", [])
        title = "SvontAI Listing Summary"
        if not rows:
            pdf = SimplePdfService.build_text_pdf(title=title, lines=["Secilen listing bulunamadi."], footer="SvontAI Real Estate Pack")
            return summary, pdf, "listing-summary-empty.pdf"

        lines: list[str] = []
        for index, item in enumerate(rows, start=1):
            lines.append(f"{index}) {item['title']}")
            lines.append(f"   Bolge: {item['location_text']} | Fiyat: {item['price']} {item['currency']}")
            if item.get("rooms") or item.get("m2"):
                lines.append(f"   Plan: {item.get('rooms') or '-'} | m2: {item.get('m2') or '-'}")
            lines.append(f"   Analiz: {item.get('price_analysis_note')}")
            lines.append(f"   Lokasyon Notu: {item.get('location_note')}")
            if item.get("url"):
                lines.append(f"   Link/QR Hedefi: {item['url']}")
            lines.append("")

        pdf = SimplePdfService.build_text_pdf(
            title=title,
            lines=lines,
            footer="Rapor yalnizca tenant ilan verisinden uretilmistir.",
        )
        filename = f"listing-summary-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.pdf"
        return summary, pdf, filename

    async def send_listing_summary_pdf_to_lead(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        pdf_bytes: bytes,
        filename: str,
    ) -> dict[str, Any]:
        lead = self.db.query(Lead).filter(
            Lead.id == lead_id,
            Lead.tenant_id == tenant_id,
        ).first()
        if lead is None:
            raise ValueError("Lead bulunamadı")
        if not lead.conversation:
            raise ValueError("Lead için WhatsApp konuşması bulunamadı")

        account = self.db.query(WhatsAppAccount).filter(
            WhatsAppAccount.tenant_id == tenant_id,
            WhatsAppAccount.is_active.is_(True),
        ).first()
        if not account:
            raise ValueError("Aktif WhatsApp hesabı bulunamadı")

        access_token = decrypt_token(account.access_token_encrypted) if account.access_token_encrypted else None
        if not access_token:
            raise ValueError("WhatsApp access token çözümlenemedi")

        upload_result = await meta_api_service.upload_media(
            access_token=access_token,
            phone_number_id=account.phone_number_id,
            filename=filename,
            content_bytes=pdf_bytes,
            mime_type="application/pdf",
        )
        media_id = upload_result.get("id")

        send_result = await meta_api_service.send_document_message(
            access_token=access_token,
            phone_number_id=account.phone_number_id,
            to=lead.conversation.external_user_id,
            media_id=media_id,
            filename=filename,
            caption="Size uygun ilan özeti raporunu iletiyorum.",
        )
        SystemEventService(self.db).log(
            tenant_id=str(tenant_id),
            source="real_estate_pack",
            level="info",
            code="RE_LISTING_PDF_SENT",
            message="Listing summary PDF sent via WhatsApp",
            meta_json={"lead_id": str(lead_id), "media_id": media_id},
        )
        self.db.commit()
        return {"media_id": media_id, "send_result": send_result}

    def get_weekly_metrics(self, tenant_id: UUID) -> dict[str, Any]:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_start_dt = datetime.combine(week_start, datetime.min.time())

        lead_count = self.db.query(func.count(Lead.id)).filter(
            Lead.tenant_id == tenant_id,
            Lead.created_at >= week_start_dt,
            Lead.is_deleted.is_(False),
        ).scalar() or 0

        active_conversations = self.db.query(func.count(RealEstateConversationState.id)).filter(
            RealEstateConversationState.tenant_id == tenant_id,
            RealEstateConversationState.current_state.in_(["qualify", "match_listings", "appointment"]),
        ).scalar() or 0

        appointment_count = self.db.query(func.count(RealEstateAppointment.id)).filter(
            RealEstateAppointment.tenant_id == tenant_id,
            RealEstateAppointment.created_at >= week_start_dt,
        ).scalar() or 0

        clicked_count = self.db.query(func.count(RealEstateLeadListingEvent.id)).filter(
            RealEstateLeadListingEvent.tenant_id == tenant_id,
            RealEstateLeadListingEvent.event == "clicked",
            RealEstateLeadListingEvent.created_at >= week_start_dt,
        ).scalar() or 0

        sent_count = self.db.query(func.count(RealEstateLeadListingEvent.id)).filter(
            RealEstateLeadListingEvent.tenant_id == tenant_id,
            RealEstateLeadListingEvent.event == "sent",
            RealEstateLeadListingEvent.created_at >= week_start_dt,
        ).scalar() or 0

        states = self.db.query(RealEstateConversationState).filter(
            RealEstateConversationState.tenant_id == tenant_id
        ).all()
        location_counter: dict[str, int] = {}
        budget_buckets: dict[str, int] = {
            "0-2M": 0,
            "2M-4M": 0,
            "4M-8M": 0,
            "8M+": 0,
        }
        for state in states:
            data = state.collected_data or {}
            location = (data.get("location_text") or "").strip()
            if location:
                location_counter[location] = location_counter.get(location, 0) + 1

            budget = data.get("budget_max") or 0
            if budget <= 0:
                continue
            if budget < 2_000_000:
                budget_buckets["0-2M"] += 1
            elif budget < 4_000_000:
                budget_buckets["2M-4M"] += 1
            elif budget < 8_000_000:
                budget_buckets["4M-8M"] += 1
            else:
                budget_buckets["8M+"] += 1

        top_locations = [
            {"location": location, "count": count}
            for location, count in sorted(location_counter.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        conversion_rate = round((appointment_count / lead_count) * 100, 2) if lead_count else 0.0
        metrics = {
            "week_start": week_start.isoformat(),
            "lead_count": lead_count,
            "active_conversations": active_conversations,
            "appointment_count": appointment_count,
            "conversion_rate_percent": conversion_rate,
            "listing_sent_count": sent_count,
            "listing_clicked_count": clicked_count,
            "top_locations": top_locations,
            "budget_buckets": budget_buckets,
        }

        report = self.db.query(RealEstateWeeklyReport).filter(
            RealEstateWeeklyReport.tenant_id == tenant_id,
            RealEstateWeeklyReport.week_start == week_start,
        ).first()
        if report:
            report.metrics_json = metrics
        else:
            self.db.add(
                RealEstateWeeklyReport(
                    tenant_id=tenant_id,
                    week_start=week_start,
                    metrics_json=metrics,
                    pdf_url=None,
                )
            )
        self.db.commit()
        return metrics

    def list_agents(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = self.db.query(User, Role.name).join(
            TenantMembership, TenantMembership.user_id == User.id
        ).join(
            Role, Role.id == TenantMembership.role_id
        ).filter(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.status == "active",
            User.is_active.is_(True),
        ).order_by(User.full_name.asc()).all()

        output = [
            {"id": str(user.id), "full_name": user.full_name, "email": user.email, "role": role_name}
            for user, role_name in rows
        ]
        existing_ids = {item["id"] for item in output}

        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant:
            owner = self.db.query(User).filter(User.id == tenant.owner_id, User.is_active.is_(True)).first()
            if owner and str(owner.id) not in existing_ids:
                output.append(
                    {"id": str(owner.id), "full_name": owner.full_name, "email": owner.email, "role": "owner"}
                )

        return sorted(output, key=lambda item: (item.get("full_name") or "").lower())

    def build_seller_service_report(self, tenant_id: UUID, lead_id: UUID, days: int = 7) -> dict[str, Any]:
        lead = self.db.query(Lead).filter(
            Lead.id == lead_id,
            Lead.tenant_id == tenant_id,
            Lead.is_deleted.is_(False),
        ).first()
        if not lead:
            raise ValueError("Lead bulunamadı")

        since = datetime.utcnow() - timedelta(days=days)
        views = self.db.query(func.count(RealEstateLeadListingEvent.id)).filter(
            RealEstateLeadListingEvent.tenant_id == tenant_id,
            RealEstateLeadListingEvent.lead_id == lead_id,
            RealEstateLeadListingEvent.created_at >= since,
            RealEstateLeadListingEvent.event.in_(["viewed", "clicked", "sent"]),
        ).scalar() or 0
        meetings = self.db.query(func.count(RealEstateAppointment.id)).filter(
            RealEstateAppointment.tenant_id == tenant_id,
            RealEstateAppointment.lead_id == lead_id,
            RealEstateAppointment.created_at >= since,
        ).scalar() or 0
        offers = self.db.query(func.count(RealEstateLeadListingEvent.id)).filter(
            RealEstateLeadListingEvent.tenant_id == tenant_id,
            RealEstateLeadListingEvent.lead_id == lead_id,
            RealEstateLeadListingEvent.created_at >= since,
            RealEstateLeadListingEvent.event == "offer",
        ).scalar() or 0

        report_text = (
            f"Bu hafta portföyünüz için {views} görüntülenme/etkileşim, "
            f"{meetings} görüşme ve {offers} teklif kaydı oluştu."
        )
        return {
            "lead_id": str(lead_id),
            "days": days,
            "views": int(views),
            "meetings": int(meetings),
            "offers": int(offers),
            "text": report_text,
        }

    async def send_seller_service_report(self, tenant_id: UUID, lead_id: UUID) -> dict[str, Any]:
        lead = self.db.query(Lead).filter(
            Lead.id == lead_id,
            Lead.tenant_id == tenant_id,
        ).first()
        if not lead or not lead.conversation:
            raise ValueError("Satıcı lead veya konuşma bulunamadı")

        report = self.build_seller_service_report(tenant_id, lead_id)
        account = self.db.query(WhatsAppAccount).filter(
            WhatsAppAccount.tenant_id == tenant_id,
            WhatsAppAccount.is_active.is_(True),
        ).first()
        if not account:
            raise ValueError("Aktif WhatsApp hesabı bulunamadı")

        access_token = decrypt_token(account.access_token_encrypted) if account.access_token_encrypted else None
        if not access_token:
            raise ValueError("WhatsApp access token çözümlenemedi")

        state = self.db.query(RealEstateConversationState).filter(
            RealEstateConversationState.conversation_id == lead.conversation_id
        ).first()
        now = datetime.utcnow()
        use_template = bool(state and state.window_open_until and now > state.window_open_until)
        send_result: dict[str, Any]

        if use_template:
            template = self.db.query(RealEstateTemplateRegistry).filter(
                RealEstateTemplateRegistry.tenant_id == tenant_id,
                RealEstateTemplateRegistry.category == "seller",
                RealEstateTemplateRegistry.is_approved.is_(True),
                RealEstateTemplateRegistry.meta_template_id.isnot(None),
            ).order_by(RealEstateTemplateRegistry.updated_at.desc()).first()
            if template:
                send_result = await meta_api_service.send_template_message(
                    access_token=access_token,
                    phone_number_id=account.phone_number_id,
                    to=lead.conversation.external_user_id,
                    template_name=template.meta_template_id,
                    language_code=template.language or "tr",
                )
            else:
                send_result = await meta_api_service.send_text_message(
                    access_token=access_token,
                    phone_number_id=account.phone_number_id,
                    to=lead.conversation.external_user_id,
                    text=report["text"],
                )
        else:
            send_result = await meta_api_service.send_text_message(
                access_token=access_token,
                phone_number_id=account.phone_number_id,
                to=lead.conversation.external_user_id,
                text=report["text"],
            )

        lead.extra_data = {
            **(lead.extra_data or {}),
            "seller_service_report_last_sent_at": now.isoformat(),
            "seller_service_report_last": report,
            "seller_service_report_due": False,
        }
        self.db.commit()
        return {"report": report, "send_result": send_result}

    async def dispatch_seller_reports_if_due(self, tenant_id: UUID) -> dict[str, int]:
        leads = self.db.query(Lead).filter(
            Lead.tenant_id == tenant_id,
            Lead.is_deleted.is_(False),
        ).all()
        due_leads: list[Lead] = []
        now = datetime.utcnow()
        for lead in leads:
            tags = set(lead.tags or [])
            if "seller" not in tags:
                continue
            extra = lead.extra_data or {}
            last_sent_raw = extra.get("seller_service_report_last_sent_at")
            if extra.get("seller_service_report_due") is True:
                due_leads.append(lead)
                continue
            if not last_sent_raw:
                due_leads.append(lead)
                continue
            try:
                last_sent = datetime.fromisoformat(last_sent_raw)
            except Exception:
                due_leads.append(lead)
                continue
            if now - last_sent >= timedelta(days=7):
                due_leads.append(lead)

        sent = 0
        failed = 0
        for lead in due_leads:
            try:
                await self.send_seller_service_report(tenant_id, lead.id)
                sent += 1
            except Exception:
                failed += 1
        return {"due": len(due_leads), "sent": sent, "failed": failed}

    def generate_weekly_report_pdf(self, tenant_id: UUID) -> tuple[dict[str, Any], bytes]:
        metrics = self.get_weekly_metrics(tenant_id)
        top_locations = metrics.get("top_locations") or []
        lines = [
            f"Lead: {metrics.get('lead_count', 0)}",
            f"Aktif Konusma: {metrics.get('active_conversations', 0)}",
            f"Randevu: {metrics.get('appointment_count', 0)}",
            f"Donusum: %{metrics.get('conversion_rate_percent', 0)}",
            f"Listing Sent: {metrics.get('listing_sent_count', 0)}",
            f"Listing Clicked: {metrics.get('listing_clicked_count', 0)}",
            "",
            "Top Bolgeler:",
        ]
        for row in top_locations:
            lines.append(f"- {row.get('location')}: {row.get('count')}")

        pdf = SimplePdfService.build_text_pdf(
            title=f"Real Estate Weekly Report - {metrics.get('week_start')}",
            lines=lines,
            footer="SvontAI Real Estate Pack",
        )
        return metrics, pdf

    def dispatch_weekly_report_if_due(self, tenant_id: UUID, force: bool = False) -> dict[str, Any]:
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant is None:
            return {"sent": False, "reason": "tenant_not_found"}

        now = datetime.utcnow()
        if (
            not force
            and (
                now.weekday() != settings.REAL_ESTATE_WEEKLY_REPORT_DAY
                or now.hour < settings.REAL_ESTATE_WEEKLY_REPORT_HOUR_UTC
            )
        ):
            return {"sent": False, "reason": "not_schedule_window"}

        week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
        last_sent_week = (tenant.settings or {}).get("real_estate_weekly_report_last_week")
        if not force and last_sent_week == week_start:
            return {"sent": False, "reason": "already_sent_this_week"}

        metrics, pdf = self.generate_weekly_report_pdf(tenant_id)
        agents = self.list_agents(tenant_id)
        recipients = [agent["email"] for agent in agents if agent.get("email")]
        if tenant.owner and tenant.owner.email:
            recipients.append(tenant.owner.email)
        recipients = sorted(set(recipients))
        if not recipients:
            return {"sent": False, "reason": "no_recipients"}

        sent = EmailService.send_real_estate_weekly_report_email(
            recipients=recipients,
            tenant_name=tenant.name,
            week_start=week_start,
            metrics=metrics,
            pdf_bytes=pdf,
        )
        if not sent:
            return {"sent": False, "reason": "email_send_failed"}

        tenant.settings = {**(tenant.settings or {}), "real_estate_weekly_report_last_week": week_start}
        report = self.db.query(RealEstateWeeklyReport).filter(
            RealEstateWeeklyReport.tenant_id == tenant_id,
            RealEstateWeeklyReport.week_start == date.fromisoformat(week_start),
        ).first()
        if report:
            report.pdf_url = f"generated://weekly/{week_start}"
        self.db.commit()
        return {"sent": True, "recipients": len(recipients), "week_start": week_start}

    def get_enabled_tenant_ids(self) -> list[UUID]:
        from_settings = [
            row[0]
            for row in self.db.query(RealEstatePackSettings.tenant_id).filter(
                RealEstatePackSettings.enabled.is_(True)
            ).all()
        ]
        from_flags = [
            row[0]
            for row in self.db.query(FeatureFlag.tenant_id).filter(
                FeatureFlag.key == "real_estate_pack",
                FeatureFlag.enabled.is_(True),
                FeatureFlag.tenant_id.isnot(None),
            ).all()
        ]
        return sorted(set([*from_settings, *from_flags]), key=lambda value: str(value))

    async def run_automation_cycle(self) -> dict[str, Any]:
        tenant_ids = self.get_enabled_tenant_ids()
        followup_total = {"pending": 0, "sent": 0, "skipped": 0, "failed": 0}
        weekly_sent = 0

        for tenant_id in tenant_ids:
            followup_stats = await self.run_followups(tenant_id)
            for key in followup_total:
                followup_total[key] += int(followup_stats.get(key, 0))
            weekly = self.dispatch_weekly_report_if_due(tenant_id)
            if weekly.get("sent"):
                weekly_sent += 1
            await self.dispatch_seller_reports_if_due(tenant_id)

        return {
            "tenant_count": len(tenant_ids),
            "followups": followup_total,
            "weekly_reports_sent": weekly_sent,
        }
