"""Secure media library and AI media-action handling."""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.artifact import Artifact
from app.models.assistant_media import AssistantMediaAsset
from app.models.conversation import Conversation
from app.models.message import Message, MessageSender
from app.services.artifact_service import ArtifactService


logger = logging.getLogger(__name__)


ALLOWED_MEDIA: dict[str, tuple[str, str]] = {
    "image/jpeg": ("image", ".jpg"),
    "image/png": ("image", ".png"),
    "image/webp": ("image", ".webp"),
    "video/mp4": ("video", ".mp4"),
    "application/pdf": ("catalog", ".pdf"),
}
MEDIA_LIBRARY_LIMIT = 100
MEDIA_ACTION_PATTERN = re.compile(r"<svontai_action>\s*(\{.*?\})\s*</svontai_action>", re.DOTALL)


@dataclass(slots=True)
class SelectedMedia:
    asset: AssistantMediaAsset
    caption: str | None


class AssistantMediaService:
    def __init__(self, db: Session):
        self.db = db
        self.artifacts = ArtifactService(db)

    @staticmethod
    def detect_media(data: bytes) -> tuple[str, str]:
        if data.startswith(b"\xff\xd8\xff"):
            return "image", "image/jpeg"
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image", "image/png"
        if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "image", "image/webp"
        if len(data) >= 12 and data[4:8] == b"ftyp":
            return "video", "video/mp4"
        if data.startswith(b"%PDF-"):
            return "catalog", "application/pdf"
        raise ValueError("Dosya içeriği desteklenen JPEG, PNG, WebP, MP4 veya PDF biçiminde değil.")

    @staticmethod
    def normalize_keywords(values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values[:12]:
            item = str(value).strip()[:60]
            key = item.casefold()
            if item and key not in seen:
                normalized.append(item)
                seen.add(key)
        return normalized

    def create(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        description: str | None,
        keywords: list[str],
        filename: str,
        claimed_mime_type: str | None,
        data: bytes,
    ) -> AssistantMediaAsset:
        if self.db.query(AssistantMediaAsset).filter(AssistantMediaAsset.tenant_id == tenant_id).count() >= MEDIA_LIBRARY_LIMIT:
            raise ValueError(f"Bir işletme en fazla {MEDIA_LIBRARY_LIMIT} medya dosyası saklayabilir.")

        media_type, mime_type = self.detect_media(data)
        if claimed_mime_type and claimed_mime_type.lower() not in {mime_type, "application/octet-stream"}:
            raise ValueError("Dosyanın bildirilen türü ile gerçek içeriği uyuşmuyor.")

        safe_title = title.strip()[:160]
        if not safe_title:
            raise ValueError("Medya adı gerekli.")
        extension = ALLOWED_MEDIA[mime_type][1]
        artifact = self.artifacts.persist_bytes(
            tenant_id=tenant_id,
            request_id=f"media-{uuid.uuid4().hex}",
            tool_slug="assistant-media",
            artifact_type=media_type,
            file_name=f"{safe_title}{extension}",
            data=data,
            content_type=mime_type,
            meta={"original_filename": filename[:255]},
        )
        asset = AssistantMediaAsset(
            tenant_id=tenant_id,
            artifact_id=artifact.id,
            created_by=user_id,
            title=safe_title,
            description=(description or "").strip()[:1200] or None,
            media_type=media_type,
            mime_type=mime_type,
            file_size_bytes=len(data),
            keywords=self.normalize_keywords(keywords),
            is_active=True,
        )
        try:
            self.db.add(asset)
            self.db.commit()
            self.db.refresh(asset)
        except Exception:
            self.db.rollback()
            try:
                self.artifacts.delete_artifact_bytes(artifact)
            except Exception as cleanup_exc:
                logger.warning(
                    "Assistant media object cleanup failed after database error: %s",
                    type(cleanup_exc).__name__,
                )
            try:
                persisted_artifact = self.db.query(Artifact).filter(Artifact.id == artifact.id).first()
                if persisted_artifact is not None:
                    self.db.delete(persisted_artifact)
                    self.db.commit()
            except Exception as cleanup_exc:
                self.db.rollback()
                logger.warning(
                    "Assistant media artifact row cleanup failed: %s",
                    type(cleanup_exc).__name__,
                )
            raise
        return asset

    def list(self, tenant_id: uuid.UUID) -> list[AssistantMediaAsset]:
        return self.db.query(AssistantMediaAsset).filter(
            AssistantMediaAsset.tenant_id == tenant_id
        ).order_by(AssistantMediaAsset.created_at.desc()).all()

    def get(self, tenant_id: uuid.UUID, asset_id: uuid.UUID) -> AssistantMediaAsset | None:
        return self.db.query(AssistantMediaAsset).filter(
            AssistantMediaAsset.id == asset_id,
            AssistantMediaAsset.tenant_id == tenant_id,
        ).first()

    def active_count(self, tenant_id: uuid.UUID) -> int:
        return self.db.query(AssistantMediaAsset).filter(
            AssistantMediaAsset.tenant_id == tenant_id,
            AssistantMediaAsset.is_active.is_(True),
        ).count()

    def artifact_for(self, asset: AssistantMediaAsset) -> Artifact:
        artifact = self.db.query(Artifact).filter(
            Artifact.id == asset.artifact_id,
            Artifact.tenant_id == asset.tenant_id,
        ).first()
        if artifact is None:
            raise ValueError("Medya dosyası depolamada bulunamadı.")
        return artifact

    def response_data(self, asset: AssistantMediaAsset) -> dict:
        artifact = self.artifact_for(asset)
        preview = self.artifacts.to_response_artifact(artifact)
        return {
            "id": asset.id,
            "title": asset.title,
            "description": asset.description,
            "media_type": asset.media_type,
            "mime_type": asset.mime_type,
            "file_size_bytes": asset.file_size_bytes,
            "keywords": asset.keywords or [],
            "is_active": asset.is_active,
            "send_count": asset.send_count,
            "last_sent_at": asset.last_sent_at,
            "preview_url": preview.url,
            "created_at": asset.created_at,
            "updated_at": asset.updated_at,
        }

    def delete(self, asset: AssistantMediaAsset) -> None:
        artifact = self.artifact_for(asset)
        self.artifacts.delete_artifact_bytes(artifact)
        self.db.delete(asset)
        self.db.delete(artifact)
        self.db.commit()

    def build_ai_context(self, tenant_id: uuid.UUID) -> str:
        assets = self.db.query(AssistantMediaAsset).filter(
            AssistantMediaAsset.tenant_id == tenant_id,
            AssistantMediaAsset.is_active.is_(True),
        ).order_by(AssistantMediaAsset.created_at.desc()).limit(MEDIA_LIBRARY_LIMIT).all()
        if not assets:
            return ""
        lines = [
            "### DOĞRULANMIŞ MEDYA KÜTÜPHANESİ",
            "Müşteri açıkça görsel, video veya katalog isterse yalnızca aşağıdaki varlıklardan en uygun TEK varlığı seç.",
            "Göndermek için normal yanıtının EN SONUNA şu biçimde tek satır ekle:",
            '<svontai_action>{"type":"send_media","asset_id":"UUID","caption":"kısa açıklama"}</svontai_action>',
            "Bu teknik etiketten müşteriye bahsetme. Talep yoksa medya eylemi üretme. Varlık kimliği uydurma.",
        ]
        for asset in assets:
            details = " | ".join(filter(None, [
                f"asset_id={asset.id}",
                f"tür={asset.media_type}",
                f"ad={asset.title}",
                f"açıklama={asset.description or ''}",
                f"anahtarlar={', '.join(asset.keywords or [])}",
            ]))
            lines.append(f"- {details}")
        return "\n".join(lines)

    def extract_action(
        self,
        *,
        tenant_id: uuid.UUID,
        conversation: Conversation,
        reply: str,
    ) -> tuple[str, SelectedMedia | None]:
        matches = list(MEDIA_ACTION_PATTERN.finditer(reply or ""))
        clean_reply = MEDIA_ACTION_PATTERN.sub("", reply or "").strip()
        if not matches:
            return clean_reply, None
        try:
            payload = json.loads(matches[-1].group(1))
            if payload.get("type") != "send_media":
                return clean_reply, None
            asset_id = uuid.UUID(str(payload.get("asset_id")))
        except (ValueError, TypeError, json.JSONDecodeError):
            return clean_reply, None

        asset = self.get(tenant_id, asset_id)
        if asset is None or not asset.is_active:
            return clean_reply, None
        duplicate = self.db.query(Message).filter(
            Message.conversation_id == conversation.id,
            Message.sender == MessageSender.BOT.value,
        ).order_by(Message.created_at.desc()).limit(20).all()
        if any(str((message.raw_payload or {}).get("media_asset_id") or "") == str(asset.id) for message in duplicate):
            return clean_reply, None
        caption = str(payload.get("caption") or "").strip()[:1024] or None
        return clean_reply, SelectedMedia(asset=asset, caption=caption)

    def mark_sent(self, asset: AssistantMediaAsset) -> None:
        asset.send_count = int(asset.send_count or 0) + 1
        asset.last_sent_at = utc_now_naive()
        self.db.commit()
