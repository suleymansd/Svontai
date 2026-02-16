"""
Real Estate Pack orchestration service (MVP).
"""

from __future__ import annotations

import json
import csv
import io
import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, date, time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import httpx
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
    "google_sheets": {
        "enabled": False,
        "auto_sync": False,
        "sync_interval_minutes": 60,
        "sheet_url": "",
        "gid": "",
        "csv_url": "",
        "mapping": {},
        "deactivate_missing": False,
        "last_sync_at": None,
    },
    "remax_connector": {
        "enabled": False,
        "auto_sync": False,
        "sync_interval_minutes": 60,
        "endpoint_url": "",
        "response_path": "data.listings",
        "mapping": {},
        "deactivate_missing": False,
        "api_key_encrypted": "",
        "last_sync_at": None,
    },
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
        self._storage_base = Path("storage/real_estate")

    @staticmethod
    def _month_key(now: datetime | None = None) -> str:
        value = now or datetime.utcnow()
        return value.strftime("%Y-%m")

    @staticmethod
    def _month_start(now: datetime | None = None) -> datetime:
        value = now or datetime.utcnow()
        return datetime(value.year, value.month, 1)

    def _get_tenant(self, tenant_id: UUID) -> Tenant | None:
        return self.db.query(Tenant).filter(Tenant.id == tenant_id).first()

    def _get_usage_counter(self, tenant_id: UUID, metric: str, month_key: str | None = None) -> int:
        tenant = self._get_tenant(tenant_id)
        if not tenant:
            return 0
        target_month = month_key or self._month_key()
        usage_root = (tenant.settings or {}).get("real_estate_usage") or {}
        month_usage = usage_root.get(target_month) or {}
        try:
            return int(month_usage.get(metric, 0))
        except Exception:
            return 0

    def _set_usage_counter(
        self,
        tenant_id: UUID,
        metric: str,
        value: int,
        month_key: str | None = None,
    ) -> None:
        tenant = self._get_tenant(tenant_id)
        if not tenant:
            return
        target_month = month_key or self._month_key()
        settings_json = dict(tenant.settings or {})
        usage_root = dict(settings_json.get("real_estate_usage") or {})
        month_usage = dict(usage_root.get(target_month) or {})
        month_usage[metric] = int(max(0, value))
        usage_root[target_month] = month_usage
        settings_json["real_estate_usage"] = usage_root
        tenant.settings = settings_json

    def _increment_usage_counter(
        self,
        tenant_id: UUID,
        metric: str,
        amount: int = 1,
        month_key: str | None = None,
    ) -> int:
        current = self._get_usage_counter(tenant_id, metric, month_key=month_key)
        next_value = current + amount
        self._set_usage_counter(tenant_id, metric, next_value, month_key=month_key)
        return next_value

    def _seed_usage_counter_if_missing(
        self,
        tenant_id: UUID,
        metric: str,
        fallback_value: int,
        month_key: str | None = None,
    ) -> int:
        current = self._get_usage_counter(tenant_id, metric, month_key=month_key)
        if current <= 0 and fallback_value > 0:
            self._set_usage_counter(tenant_id, metric, fallback_value, month_key=month_key)
            return fallback_value
        return current

    def _storage_path(self, relative_path: str) -> Path:
        return self._storage_base / relative_path

    def _write_storage_file(self, relative_path: str, content: bytes) -> str:
        file_path = self._storage_path(relative_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        return relative_path

    def read_storage_file(self, relative_path: str) -> bytes:
        file_path = self._storage_path(relative_path)
        if not file_path.exists():
            raise FileNotFoundError(relative_path)
        return file_path.read_bytes()

    @staticmethod
    def _parse_hhmm(value: str, fallback: time) -> time:
        try:
            hour_part, minute_part = value.strip().split(":")
            return time(hour=int(hour_part), minute=int(minute_part))
        except Exception:
            return fallback

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

    @staticmethod
    def _extract_json_path(payload: Any, path: str | None) -> Any:
        if not path:
            return payload
        current = payload
        for part in [item.strip() for item in path.split(".") if item.strip()]:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except Exception:
                    return None
            else:
                return None
        return current

    @staticmethod
    def _normalize_listing_source_config(raw_source: Any) -> dict[str, Any]:
        source = json.loads(json.dumps(DEFAULT_LISTING_SOURCE))
        candidate = dict(raw_source or {})

        source["manual"] = bool(candidate.get("manual", source["manual"]))
        source["csv_import"] = bool(candidate.get("csv_import", source["csv_import"]))

        google_raw = candidate.get("google_sheets", {})
        if isinstance(google_raw, bool):
            google_raw = {"enabled": google_raw}
        google_cfg = dict(source["google_sheets"])
        if isinstance(google_raw, dict):
            google_cfg.update({k: v for k, v in google_raw.items() if v is not None})
        google_cfg["enabled"] = bool(google_cfg.get("enabled", False))
        google_cfg["auto_sync"] = bool(google_cfg.get("auto_sync", False))
        google_cfg["sync_interval_minutes"] = max(5, int(google_cfg.get("sync_interval_minutes") or 60))
        google_cfg["mapping"] = dict(google_cfg.get("mapping") or {})
        source["google_sheets"] = google_cfg

        remax_raw = candidate.get("remax_connector", {})
        if isinstance(remax_raw, bool):
            remax_raw = {"enabled": remax_raw}
        remax_cfg = dict(source["remax_connector"])
        if isinstance(remax_raw, dict):
            remax_cfg.update({k: v for k, v in remax_raw.items() if v is not None})
        remax_cfg["enabled"] = bool(remax_cfg.get("enabled", False))
        remax_cfg["auto_sync"] = bool(remax_cfg.get("auto_sync", False))
        remax_cfg["sync_interval_minutes"] = max(5, int(remax_cfg.get("sync_interval_minutes") or 60))
        remax_cfg["mapping"] = dict(remax_cfg.get("mapping") or {})
        source["remax_connector"] = remax_cfg
        return source

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            text = str(value or "").strip()
            if not text:
                return None
            return int(float(text.replace(".", "").replace(",", ".")))
        except Exception:
            return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            text = str(value or "").strip()
            if not text:
                return None
            return float(text.replace(",", "."))
        except Exception:
            return None

    @staticmethod
    def _normalize_sale_rent(value: Any) -> str | None:
        normalized = str(value or "").strip().lower()
        if not normalized:
            return None
        if normalized in {"rent", "kiralık", "kiralik", "kira"}:
            return "rent"
        if normalized in {"sale", "satılık", "satilik", "satış", "satis"}:
            return "sale"
        return None

    def _http_get_text(self, url: str, headers: dict[str, str] | None = None) -> str:
        with httpx.Client(timeout=25.0) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.text

    def _http_get_json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        with httpx.Client(timeout=25.0) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _build_google_sheets_csv_url(config: dict[str, Any]) -> str:
        csv_url = (config.get("csv_url") or "").strip()
        if csv_url:
            return csv_url

        sheet_url = (config.get("sheet_url") or "").strip()
        if not sheet_url:
            raise ValueError("Google Sheets URL gerekli")

        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
        if not match:
            raise ValueError("Geçerli bir Google Sheets URL girin")
        spreadsheet_id = match.group(1)

        parsed = urlparse(sheet_url)
        query_gid = parse_qs(parsed.query).get("gid", [None])[0]
        gid = (config.get("gid") or query_gid or "0").strip()
        return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"

    @staticmethod
    def _read_row_value(row: dict[str, Any], key: str) -> Any:
        if key in row:
            return row.get(key)
        lowered = {str(k).strip().lower(): v for k, v in row.items()}
        return lowered.get(str(key).strip().lower())

    def _map_external_listing_row(
        self,
        row: dict[str, Any],
        mapping: dict[str, str],
    ) -> dict[str, Any] | None:
        def pick(field: str, default_field: str | None = None) -> Any:
            mapped_key = (mapping.get(field) or "").strip()
            if mapped_key:
                return self._read_row_value(row, mapped_key)
            direct = self._read_row_value(row, field)
            if direct not in (None, ""):
                return direct
            if default_field:
                return self._read_row_value(row, default_field)
            return direct

        external_id = str(pick("external_id", "id") or "").strip()
        title = str(pick("title") or "").strip()
        location_text = str(pick("location_text", "location") or "").strip()
        sale_rent = self._normalize_sale_rent(pick("sale_rent", "type")) or "sale"
        property_type = str(pick("property_type", "property_type") or "daire").strip().lower() or "daire"
        price = self._to_int(pick("price"))
        if not title or not location_text or not price or price <= 0:
            return None

        data = {
            "external_id": external_id or None,
            "title": title,
            "description": str(pick("description") or "").strip() or None,
            "sale_rent": sale_rent,
            "property_type": property_type,
            "location_text": location_text,
            "lat": self._to_float(pick("lat")),
            "lng": self._to_float(pick("lng")),
            "price": int(price),
            "currency": str(pick("currency") or "TRY").strip().upper() or "TRY",
            "m2": self._to_int(pick("m2")),
            "rooms": str(pick("rooms") or "").strip() or None,
            "url": str(pick("url") or "").strip() or None,
            "is_active": True,
        }
        return data

    def _upsert_external_listings(
        self,
        tenant_id: UUID,
        user_id: UUID,
        source_key: str,
        rows: list[dict[str, Any]],
        mapping: dict[str, str] | None = None,
        deactivate_missing: bool = False,
    ) -> dict[str, int]:
        mapped_rows = []
        skipped = 0
        for row in rows:
            if not isinstance(row, dict):
                skipped += 1
                continue
            parsed = self._map_external_listing_row(row, mapping or {})
            if parsed is None:
                skipped += 1
                continue
            mapped_rows.append(parsed)

        existing_rows = self.db.query(RealEstateListing).filter(
            RealEstateListing.tenant_id == tenant_id
        ).all()
        by_external: dict[str, RealEstateListing] = {}
        for existing in existing_rows:
            features = existing.features or {}
            if features.get("_source") != source_key:
                continue
            ext = str(features.get("_external_id") or "").strip()
            if ext:
                by_external[ext] = existing

        created = 0
        updated = 0
        processed_external_ids: set[str] = set()
        fallback_updated_ids: set[UUID] = set()

        for item in mapped_rows:
            external_id = str(item.get("external_id") or "").strip()
            target: RealEstateListing | None = None
            if external_id:
                target = by_external.get(external_id)
                processed_external_ids.add(external_id)
            if target is None and item.get("url"):
                for existing in existing_rows:
                    if existing.tenant_id == tenant_id and (existing.url or "").strip() == (item.get("url") or "").strip():
                        target = existing
                        fallback_updated_ids.add(existing.id)
                        break
            if target is None:
                target = RealEstateListing(
                    tenant_id=tenant_id,
                    created_by=user_id,
                    title=item["title"],
                    description=item.get("description"),
                    sale_rent=item["sale_rent"],
                    property_type=item["property_type"],
                    location_text=item["location_text"],
                    lat=item.get("lat"),
                    lng=item.get("lng"),
                    price=item["price"],
                    currency=item.get("currency") or "TRY",
                    m2=item.get("m2"),
                    rooms=item.get("rooms"),
                    features={
                        "_source": source_key,
                        "_external_id": external_id or None,
                    },
                    media=[],
                    url=item.get("url"),
                    is_active=True,
                )
                self.db.add(target)
                created += 1
                continue

            target.title = item["title"]
            target.description = item.get("description")
            target.sale_rent = item["sale_rent"]
            target.property_type = item["property_type"]
            target.location_text = item["location_text"]
            target.lat = item.get("lat")
            target.lng = item.get("lng")
            target.price = item["price"]
            target.currency = item.get("currency") or "TRY"
            target.m2 = item.get("m2")
            target.rooms = item.get("rooms")
            target.url = item.get("url")
            target.is_active = True
            target.features = {
                **(target.features or {}),
                "_source": source_key,
                "_external_id": external_id or (target.features or {}).get("_external_id"),
            }
            updated += 1

        deactivated = 0
        if deactivate_missing:
            for existing in existing_rows:
                features = existing.features or {}
                if features.get("_source") != source_key:
                    continue
                ext = str(features.get("_external_id") or "").strip()
                if ext:
                    if ext not in processed_external_ids and existing.is_active:
                        existing.is_active = False
                        deactivated += 1
                elif existing.id not in fallback_updated_ids and existing.is_active:
                    existing.is_active = False
                    deactivated += 1

        return {
            "created": created,
            "updated": updated,
            "deactivated": deactivated,
            "skipped": skipped,
            "total_processed": len(mapped_rows),
        }

    def upsert_settings(self, tenant_id: UUID, payload: dict[str, Any]) -> RealEstatePackSettings:
        settings = self.get_or_create_settings(tenant_id)
        if "listings_source" in payload and payload.get("listings_source") is not None:
            merged = self._normalize_listing_source_config(
                {
                    **self._normalize_listing_source_config(settings.listings_source or {}),
                    **dict(payload.get("listings_source") or {}),
                }
            )
            remax_cfg = dict(merged.get("remax_connector") or {})
            api_key_raw = (remax_cfg.get("api_key") or "").strip()
            if api_key_raw:
                remax_cfg["api_key_encrypted"] = encrypt_token(api_key_raw)
                remax_cfg["api_key"] = ""
            merged["remax_connector"] = remax_cfg
            payload["listings_source"] = merged

        for key, value in payload.items():
            if hasattr(settings, key) and value is not None:
                setattr(settings, key, value)
        self.db.commit()
        self.db.refresh(settings)
        self.ensure_pack_feature_flag(tenant_id, settings.enabled)
        self.ensure_default_templates(tenant_id)
        return settings

    def sync_listings_from_google_sheets(
        self,
        tenant_id: UUID,
        user_id: UUID,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        settings = self.get_or_create_settings(tenant_id)
        save_to_settings = bool(config.get("save_to_settings", True))
        source_config = self._normalize_listing_source_config(settings.listings_source or {})
        current_cfg = dict(source_config.get("google_sheets") or {})
        incoming_cfg = dict(config or {})
        merged_cfg = {**current_cfg, **incoming_cfg}
        merged_cfg["mapping"] = dict(merged_cfg.get("mapping") or {})
        merged_cfg["deactivate_missing"] = bool(merged_cfg.get("deactivate_missing", False))

        csv_url = self._build_google_sheets_csv_url(merged_cfg)
        text = self._http_get_text(csv_url)
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        stats = self._upsert_external_listings(
            tenant_id=tenant_id,
            user_id=user_id,
            source_key="google_sheets",
            rows=rows,
            mapping=merged_cfg.get("mapping") or {},
            deactivate_missing=bool(merged_cfg.get("deactivate_missing", False)),
        )
        now_iso = datetime.utcnow().isoformat()
        merged_cfg.update(
            {
                "enabled": True,
                "last_sync_at": now_iso,
                "last_result": stats,
                "csv_url": (merged_cfg.get("csv_url") or "").strip(),
                "sheet_url": (merged_cfg.get("sheet_url") or "").strip(),
            }
        )
        if save_to_settings:
            source_config["google_sheets"] = merged_cfg
            settings.listings_source = source_config
        self.db.commit()
        self.db.refresh(settings)
        return {"source": "google_sheets", "stats": stats, "synced_at": now_iso}

    def sync_listings_from_remax_connector(
        self,
        tenant_id: UUID,
        user_id: UUID,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        settings = self.get_or_create_settings(tenant_id)
        save_to_settings = bool(config.get("save_to_settings", True))
        source_config = self._normalize_listing_source_config(settings.listings_source or {})
        current_cfg = dict(source_config.get("remax_connector") or {})
        incoming_cfg = dict(config or {})
        merged_cfg = {**current_cfg, **incoming_cfg}
        merged_cfg["mapping"] = dict(merged_cfg.get("mapping") or {})
        merged_cfg["deactivate_missing"] = bool(merged_cfg.get("deactivate_missing", False))

        endpoint_url = (merged_cfg.get("endpoint_url") or "").strip()
        if not endpoint_url:
            raise ValueError("Remax endpoint URL gerekli")

        provided_api_key = (merged_cfg.get("api_key") or "").strip()
        encrypted_api_key = (merged_cfg.get("api_key_encrypted") or "").strip()
        resolved_api_key = provided_api_key
        if not resolved_api_key and encrypted_api_key:
            resolved_api_key = decrypt_token(encrypted_api_key) or ""

        auth_header = (merged_cfg.get("auth_header") or "Authorization").strip() or "Authorization"
        auth_scheme = (merged_cfg.get("auth_scheme") or "Bearer").strip()
        headers: dict[str, str] = {}
        if resolved_api_key:
            headers[auth_header] = f"{auth_scheme} {resolved_api_key}".strip()

        response_payload = self._http_get_json(endpoint_url, headers=headers or None)
        response_path = (merged_cfg.get("response_path") or "data.listings").strip()
        rows_payload = self._extract_json_path(response_payload, response_path)
        if not isinstance(rows_payload, list):
            raise ValueError("Remax response_path list dönmüyor")

        stats = self._upsert_external_listings(
            tenant_id=tenant_id,
            user_id=user_id,
            source_key="remax_connector",
            rows=rows_payload,
            mapping=merged_cfg.get("mapping") or {},
            deactivate_missing=bool(merged_cfg.get("deactivate_missing", False)),
        )
        now_iso = datetime.utcnow().isoformat()
        if provided_api_key:
            merged_cfg["api_key_encrypted"] = encrypt_token(provided_api_key)
        merged_cfg["api_key"] = ""
        merged_cfg.update(
            {
                "enabled": True,
                "last_sync_at": now_iso,
                "last_result": stats,
                "endpoint_url": endpoint_url,
                "response_path": response_path,
            }
        )
        if save_to_settings:
            source_config["remax_connector"] = merged_cfg
            settings.listings_source = source_config
        self.db.commit()
        self.db.refresh(settings)
        return {"source": "remax_connector", "stats": stats, "synced_at": now_iso}

    @staticmethod
    def _is_connector_sync_due(config: dict[str, Any], now: datetime) -> bool:
        if not bool(config.get("enabled")) or not bool(config.get("auto_sync")):
            return False
        last_sync_raw = str(config.get("last_sync_at") or "").strip()
        if not last_sync_raw:
            return True
        try:
            last_sync = datetime.fromisoformat(last_sync_raw)
        except Exception:
            return True
        interval_minutes = max(5, int(config.get("sync_interval_minutes") or 60))
        return now - last_sync >= timedelta(minutes=interval_minutes)

    def run_connector_auto_sync(self, tenant_id: UUID) -> dict[str, Any]:
        settings = self.get_or_create_settings(tenant_id)
        source_config = self._normalize_listing_source_config(settings.listings_source or {})
        tenant = self._get_tenant(tenant_id)
        owner_id = tenant.owner_id if tenant else None
        if owner_id is None:
            return {"google_sheets": {"status": "skipped", "reason": "owner_not_found"}, "remax_connector": {"status": "skipped", "reason": "owner_not_found"}}

        now = datetime.utcnow()
        result: dict[str, Any] = {
            "google_sheets": {"status": "skipped", "reason": "disabled"},
            "remax_connector": {"status": "skipped", "reason": "disabled"},
        }

        google_cfg = dict(source_config.get("google_sheets") or {})
        if self._is_connector_sync_due(google_cfg, now):
            try:
                sync_result = self.sync_listings_from_google_sheets(
                    tenant_id=tenant_id,
                    user_id=owner_id,
                    config={**google_cfg, "save_to_settings": True},
                )
                result["google_sheets"] = {"status": "ok", **sync_result}
            except Exception as exc:
                result["google_sheets"] = {"status": "error", "error": str(exc)}
                SystemEventService(self.db).log(
                    tenant_id=str(tenant_id),
                    source="real_estate_pack",
                    level="warn",
                    code="RE_GOOGLE_SHEETS_SYNC_FAILED",
                    message=str(exc)[:500],
                    meta_json={"connector": "google_sheets"},
                )
        elif bool(google_cfg.get("enabled")) and bool(google_cfg.get("auto_sync")):
            result["google_sheets"] = {"status": "skipped", "reason": "not_due"}

        remax_cfg = dict(source_config.get("remax_connector") or {})
        if self._is_connector_sync_due(remax_cfg, now):
            try:
                sync_result = self.sync_listings_from_remax_connector(
                    tenant_id=tenant_id,
                    user_id=owner_id,
                    config={**remax_cfg, "save_to_settings": True},
                )
                result["remax_connector"] = {"status": "ok", **sync_result}
            except Exception as exc:
                result["remax_connector"] = {"status": "error", "error": str(exc)}
                SystemEventService(self.db).log(
                    tenant_id=str(tenant_id),
                    source="real_estate_pack",
                    level="warn",
                    code="RE_REMAX_SYNC_FAILED",
                    message=str(exc)[:500],
                    meta_json={"connector": "remax_connector"},
                )
        elif bool(remax_cfg.get("enabled")) and bool(remax_cfg.get("auto_sync")):
            result["remax_connector"] = {"status": "skipped", "reason": "not_due"}

        return result

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
            settings = self.get_or_create_settings(tenant_id)
            month_start = self._month_start()
            historical_count = self.db.query(func.count(Lead.id)).filter(
                Lead.tenant_id == tenant_id,
                Lead.created_at >= month_start,
                Lead.is_deleted.is_(False),
            ).scalar() or 0
            usage_count = self._seed_usage_counter_if_missing(
                tenant_id=tenant_id,
                metric="lead_created",
                fallback_value=int(historical_count),
            )
            if usage_count >= settings.lead_limit_monthly:
                raise ValueError("lead_limit_reached")

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
            self._increment_usage_counter(tenant_id, "lead_created", amount=1)
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
        try:
            lead = self._upsert_lead(tenant_id, bot, conversation, from_number, contact_name)
        except ValueError as exc:
            if str(exc) == "lead_limit_reached":
                return RealEstateMessageResult(
                    handled=True,
                    response_text="Bu ay lead limitinize ulaştınız. Yeni lead işlemek için paket limitinizi yükseltin.",
                )
            raise
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

        month_start = self._month_start(now)
        historical_sent_count = self.db.query(func.count(RealEstateFollowUpJob.id)).filter(
            RealEstateFollowUpJob.tenant_id == tenant_id,
            RealEstateFollowUpJob.status == "sent",
            RealEstateFollowUpJob.sent_at.isnot(None),
            RealEstateFollowUpJob.sent_at >= month_start,
        ).scalar() or 0
        usage_sent_count = self._seed_usage_counter_if_missing(
            tenant_id=tenant_id,
            metric="followup_sent",
            fallback_value=int(historical_sent_count),
            month_key=self._month_key(now),
        )

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
            if usage_sent_count >= settings.followup_limit_monthly:
                job.status = "skipped"
                job.error_text = "followup_limit_reached"
                skipped += 1
                continue

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
                usage_sent_count = self._increment_usage_counter(
                    tenant_id=tenant_id,
                    metric="followup_sent",
                    amount=1,
                    month_key=self._month_key(now),
                )

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
        settings = self.get_or_create_settings(tenant_id)
        now = datetime.utcnow()
        month_key = self._month_key(now)
        usage_pdf = self._get_usage_counter(tenant_id, "pdf_generated", month_key=month_key)
        if usage_pdf >= settings.pdf_limit_monthly:
            raise ValueError("pdf_limit_reached")

        summary = self.build_listing_summary(tenant_id, listing_ids, lead_id=lead_id)
        rows = summary.get("items", [])
        title = "SvontAI Listing Summary"
        if not rows:
            pdf = SimplePdfService.build_text_pdf(title=title, lines=["Secilen listing bulunamadi."], footer="SvontAI Real Estate Pack")
            self._increment_usage_counter(tenant_id, "pdf_generated", amount=1, month_key=month_key)
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
        self._increment_usage_counter(tenant_id, "pdf_generated", amount=1, month_key=month_key)
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

    def get_available_slots(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        *,
        start_at: datetime,
        end_at: datetime,
        duration_minutes: int = 60,
        step_minutes: int = 30,
    ) -> list[dict[str, str]]:
        settings = self.get_or_create_settings(tenant_id)
        duration = timedelta(minutes=max(15, duration_minutes))
        step = timedelta(minutes=max(15, step_minutes))

        raw_windows = settings.manual_availability or []
        windows: list[dict[str, Any]] = []
        for row in raw_windows:
            if not isinstance(row, dict):
                continue
            windows.append(
                {
                    "weekday": int(row.get("weekday", 0)),
                    "start": self._parse_hhmm(str(row.get("start", "09:00")), fallback=time(9, 0)),
                    "end": self._parse_hhmm(str(row.get("end", "18:00")), fallback=time(18, 0)),
                }
            )
        if not windows:
            windows = [
                {"weekday": day, "start": time(9, 0), "end": time(18, 0)}
                for day in range(0, 5)
            ]

        busy_intervals: list[tuple[datetime, datetime]] = []
        if settings.google_calendar_enabled:
            try:
                busy_intervals = GoogleCalendarService(self.db).list_busy_intervals(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    time_min=start_at,
                    time_max=end_at,
                )
            except Exception as exc:
                SystemEventService(self.db).log(
                    tenant_id=str(tenant_id),
                    source="real_estate_pack",
                    level="warn",
                    code="RE_CALENDAR_BUSY_FETCH_FAILED",
                    message=str(exc)[:500],
                    meta_json={"agent_id": str(agent_id)},
                )

        def _is_busy(slot_start: datetime, slot_end: datetime) -> bool:
            for busy_start, busy_end in busy_intervals:
                if slot_start < busy_end and slot_end > busy_start:
                    return True
            return False

        output: list[dict[str, str]] = []
        cursor_date = datetime(start_at.year, start_at.month, start_at.day)
        max_slots = 120
        while cursor_date <= end_at and len(output) < max_slots:
            weekday = cursor_date.weekday()
            todays_windows = [window for window in windows if int(window["weekday"]) == weekday]
            for window in todays_windows:
                day_start = datetime.combine(cursor_date.date(), window["start"])
                day_end = datetime.combine(cursor_date.date(), window["end"])
                slot_start = max(day_start, start_at)
                while slot_start + duration <= day_end and slot_start + duration <= end_at and len(output) < max_slots:
                    slot_end = slot_start + duration
                    if not _is_busy(slot_start, slot_end):
                        output.append(
                            {
                                "start_at": slot_start.isoformat(),
                                "end_at": slot_end.isoformat(),
                            }
                        )
                    slot_start += step
            cursor_date += timedelta(days=1)

        return output

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
        settings = self.get_or_create_settings(tenant_id)
        now = datetime.utcnow()
        month_key = self._month_key(now)
        usage_pdf = self._get_usage_counter(tenant_id, "pdf_generated", month_key=month_key)
        if usage_pdf >= settings.pdf_limit_monthly:
            raise ValueError("pdf_limit_reached")

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
        self._increment_usage_counter(tenant_id, "pdf_generated", amount=1, month_key=month_key)
        return metrics, pdf

    @staticmethod
    def _weekly_report_relative_path(tenant_id: UUID, week_start: str) -> str:
        safe_week = week_start.replace("/", "-")
        return f"weekly/{tenant_id}/{safe_week}.pdf"

    def get_weekly_report_file(self, tenant_id: UUID, week_start: str) -> tuple[str, bytes]:
        report = self.db.query(RealEstateWeeklyReport).filter(
            RealEstateWeeklyReport.tenant_id == tenant_id,
            RealEstateWeeklyReport.week_start == date.fromisoformat(week_start),
        ).first()
        if not report or not report.pdf_url:
            raise FileNotFoundError("weekly_report_not_found")
        if report.pdf_url.startswith("generated://"):
            raise FileNotFoundError("weekly_report_not_stored")
        return report.pdf_url, self.read_storage_file(report.pdf_url)

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

        try:
            metrics, pdf = self.generate_weekly_report_pdf(tenant_id)
        except ValueError as exc:
            if str(exc) == "pdf_limit_reached":
                return {"sent": False, "reason": "pdf_limit_reached"}
            raise
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
            report.pdf_url = self._weekly_report_relative_path(tenant_id, week_start)
            self._write_storage_file(report.pdf_url, pdf)
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
        connector_sync: dict[str, Any] = {}

        for tenant_id in tenant_ids:
            connector_sync[str(tenant_id)] = self.run_connector_auto_sync(tenant_id)
            followup_stats = await self.run_followups(tenant_id)
            for key in followup_total:
                followup_total[key] += int(followup_stats.get(key, 0))
            weekly = self.dispatch_weekly_report_if_due(tenant_id)
            if weekly.get("sent"):
                weekly_sent += 1
            await self.dispatch_seller_reports_if_due(tenant_id)

        return {
            "tenant_count": len(tenant_ids),
            "connector_sync": connector_sync,
            "followups": followup_total,
            "weekly_reports_sent": weekly_sent,
        }
