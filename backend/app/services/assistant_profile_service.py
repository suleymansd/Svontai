"""Single-assistant profile, guided training and expert capability management."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.models.bot import Bot
from app.models.bot_settings import BotSettings
from app.models.tenant import Tenant
from app.schemas.bot import AssistantTraining


CAPABILITY_DEFINITIONS: dict[str, dict[str, Any]] = {
    "knowledge_support": {
        "name": "Bilgi ve Destek",
        "description": "İşletme bilgilerini kullanarak soruları doğal biçimde yanıtlar.",
        "default_enabled": True,
        "locked": True,
    },
    "lead_qualification": {
        "name": "Müşteri Adayı Tanıma",
        "description": "İhtiyacı anlayıp gerekli iletişim ve talep bilgilerini toplar.",
        "default_enabled": True,
    },
    "appointment_management": {
        "name": "Randevu Yönetimi",
        "description": "Gerçek takvim uygunluğunu kontrol eder ve onaylanan randevuyu oluşturur.",
        "default_enabled": True,
    },
    "human_handoff": {
        "name": "İnsan Desteğine Devir",
        "description": "Şikayet, belirsizlik veya açık temsilci talebinde konuşmayı ekibe devreder.",
        "default_enabled": True,
    },
    "media_catalog": {
        "name": "Görsel ve Katalog Paylaşımı",
        "description": "Tanımlı ürün, hizmet veya katalog bağlantısını doğru talepte paylaşır.",
        "default_enabled": False,
    },
}

DEFAULT_TRAINING = {
    "goal": "mixed",
    "tone": "professional",
    "response_length": "balanced",
    "price_policy": "known_only",
    "handoff_mode": "automatic",
    "business_summary": "",
}

RESPONSE_LENGTH_TOKENS = {"concise": 220, "balanced": 420, "detailed": 700}


class AssistantProfileService:
    def __init__(self, db: Session):
        self.db = db

    def ensure_primary(self, tenant: Tenant) -> Bot:
        primary = self.db.query(Bot).filter(
            Bot.tenant_id == tenant.id,
            Bot.assistant_type == "primary",
        ).first()
        if primary is None:
            primary = self.db.query(Bot).filter(Bot.tenant_id == tenant.id).order_by(Bot.created_at.asc()).first()
        if primary is None:
            primary = Bot(
                tenant_id=tenant.id,
                name=f"{tenant.name} Asistanı",
                description=f"{tenant.name} için müşteri iletişimini yöneten ana asistan.",
                welcome_message="Nasıl yardımcı olabilirim?",
                language="tr",
                primary_color="#2563EB",
                widget_position="right",
                is_active=True,
                assistant_type="primary",
            )
            self.db.add(primary)
            self.db.flush()
        elif primary.assistant_type != "primary":
            primary.assistant_type = "primary"
            primary.specialist_key = None

        self.db.query(Bot).filter(
            Bot.tenant_id == tenant.id,
            Bot.id != primary.id,
            Bot.assistant_type == "primary",
        ).update(
            {Bot.assistant_type: "specialist", Bot.specialist_key: "legacy_custom"},
            synchronize_session=False,
        )
        self._ensure_settings(primary)
        self.db.commit()
        self.db.refresh(primary)
        return primary

    def _ensure_settings(self, bot: Bot) -> BotSettings:
        record = self.db.query(BotSettings).filter(BotSettings.bot_id == bot.id).first()
        if record is None:
            record = BotSettings(
                bot_id=bot.id,
                response_tone="professional",
                enable_guardrails=True,
                human_handoff_enabled=True,
                extra_settings={"managed_by_autopilot": True},
            )
            self.db.add(record)
            self.db.flush()
        return record

    @staticmethod
    def _normalized_profile(settings: BotSettings) -> dict[str, Any]:
        extra = deepcopy(settings.extra_settings or {})
        stored = extra.get("assistant_profile") if isinstance(extra.get("assistant_profile"), dict) else {}
        training = {**DEFAULT_TRAINING, **(stored.get("training") or {})}
        capabilities = stored.get("capabilities") if isinstance(stored.get("capabilities"), dict) else {}
        return {"training": training, "capabilities": deepcopy(capabilities)}

    def get_profile(self, tenant: Tenant) -> dict[str, Any]:
        bot = self.ensure_primary(tenant)
        settings = self._ensure_settings(bot)
        profile = self._normalized_profile(settings)
        capabilities = [
            self._capability_response(key, definition, profile["capabilities"].get(key) or {})
            for key, definition in CAPABILITY_DEFINITIONS.items()
        ]
        training = profile["training"]
        completed = sum(bool(training.get(key)) for key in (
            "goal", "tone", "response_length", "price_policy", "handoff_mode", "business_summary"
        ))
        return {
            "assistant": bot,
            "training": training,
            "capabilities": capabilities,
            "completion_percent": round(completed / 6 * 100),
        }

    @staticmethod
    def _capability_response(key: str, definition: dict[str, Any], stored: dict[str, Any]) -> dict[str, Any]:
        enabled = bool(stored.get("enabled", definition.get("default_enabled", False)))
        config = deepcopy(stored.get("config") or {})
        missing: list[str] = []
        if key == "media_catalog" and not config.get("items"):
            missing.append("En az bir güvenli medya veya katalog bağlantısı ekleyin")
        ready = not missing
        return {
            "key": key,
            "name": definition["name"],
            "description": definition["description"],
            "enabled": enabled,
            "ready": ready,
            "status": "active" if enabled and ready else ("needs_setup" if enabled else "disabled"),
            "missing_requirements": missing,
            "config": config,
            "locked": bool(definition.get("locked")),
        }

    def update_training(self, tenant: Tenant, payload: AssistantTraining) -> dict[str, Any]:
        bot = self.ensure_primary(tenant)
        settings = self._ensure_settings(bot)
        profile = self._normalized_profile(settings)
        profile["training"] = payload.model_dump()
        settings.response_tone = payload.tone
        settings.max_response_length = RESPONSE_LENGTH_TOKENS[payload.response_length]
        settings.human_handoff_enabled = payload.handoff_mode != "manual"
        settings.extra_settings = {
            **(settings.extra_settings or {}),
            "managed_by_autopilot": True,
            "assistant_profile": profile,
        }
        if payload.business_summary.strip():
            bot.description = payload.business_summary.strip()
        self.db.commit()
        return self.get_profile(tenant)

    def update_capability(
        self,
        tenant: Tenant,
        key: str,
        *,
        enabled: bool,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        if key not in CAPABILITY_DEFINITIONS:
            raise ValueError("Unknown assistant capability")
        definition = CAPABILITY_DEFINITIONS[key]
        if definition.get("locked") and not enabled:
            raise ValueError("The core knowledge capability cannot be disabled")
        if key == "media_catalog":
            normalized_items = []
            for item in (config.get("items") or [])[:30]:
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url") or "").strip()[:2000]
                if not url.startswith(("https://", "http://")):
                    continue
                normalized_items.append({
                    "label": str(item.get("label") or "Medya").strip()[:120],
                    "url": url,
                    "keywords": [str(value).strip()[:80] for value in (item.get("keywords") or [])[:10] if str(value).strip()],
                })
            config = {"items": normalized_items}
        bot = self.ensure_primary(tenant)
        settings = self._ensure_settings(bot)
        profile = self._normalized_profile(settings)
        profile["capabilities"][key] = {"enabled": enabled, "config": deepcopy(config)}
        settings.extra_settings = {
            **(settings.extra_settings or {}),
            "managed_by_autopilot": True,
            "assistant_profile": profile,
        }
        self.db.commit()
        return self.get_profile(tenant)

    def capability_enabled(self, bot: Bot, key: str) -> bool:
        settings = self._ensure_settings(bot)
        profile = self._normalized_profile(settings)
        stored = profile["capabilities"].get(key) or {}
        return bool(stored.get("enabled", CAPABILITY_DEFINITIONS[key].get("default_enabled", False)))

    def build_ai_context(self, bot: Bot) -> str:
        settings = self._ensure_settings(bot)
        profile = self._normalized_profile(settings)
        training = AssistantTraining(**profile["training"])
        enabled = [
            self._capability_response(key, definition, profile["capabilities"].get(key) or {})
            for key, definition in CAPABILITY_DEFINITIONS.items()
        ]
        enabled = [item for item in enabled if item["enabled"] and item["ready"]]
        lines = [
            "### ANA ASİSTAN ÇALIŞMA PROFİLİ",
            f"Ana amaç: {training.goal}",
            f"Yanıt uzunluğu: {training.response_length}",
            f"Fiyat yaklaşımı: {training.price_policy}",
            f"İnsan desteğine devir: {training.handoff_mode}",
            "Aktif uzman yetenekler: " + ", ".join(item["name"] for item in enabled),
            "Tek bir asistan gibi konuş. Uzman yeteneklerin iç işleyişinden veya yönlendirmeden müşteriye bahsetme.",
        ]
        if training.business_summary.strip():
            lines.append(f"İşletme özeti: {training.business_summary.strip()}")
        if self.capability_enabled(bot, "lead_qualification"):
            lines.append("Satın alma niyeti varsa ihtiyacı doğal sorularla netleştir; aynı anda tek soru sor.")
        if self.capability_enabled(bot, "human_handoff"):
            lines.append("Müşteri insan istediğinde, şikayet ettiğinde veya güvenilir bilgi yoksa insan desteği öner.")
        media = next((item for item in enabled if item["key"] == "media_catalog"), None)
        if media:
            lines.append("İlgili müşteri talebinde yalnızca aşağıdaki doğrulanmış bağlantıları paylaş:")
            for item in media["config"].get("items", [])[:30]:
                label = str(item.get("label") or "Medya")[:120]
                url = str(item.get("url") or "").strip()
                keywords = ", ".join(str(value) for value in (item.get("keywords") or [])[:10])
                if url.startswith(("https://", "http://")):
                    lines.append(f"- {label}: {url} | anahtar kelimeler: {keywords}")
        return "\n".join(lines)

    def build_runtime_context(self, tenant: Tenant, bot: Bot) -> str:
        parts = [self.build_ai_context(bot)]
        if self.capability_enabled(bot, "appointment_management"):
            from app.services.appointment_availability_service import AppointmentAvailabilityService

            parts.append(AppointmentAvailabilityService(self.db).build_ai_context(tenant))
        return "\n\n".join(parts)
