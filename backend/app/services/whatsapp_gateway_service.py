"""Provider-neutral outbound WhatsApp gateway."""

from __future__ import annotations

import base64
from typing import Any

from app.core.encryption import decrypt_token
from app.core.rate_limit import whatsapp_send_hour_rate_limiter, whatsapp_send_minute_rate_limiter
from app.models.whatsapp_account import WhatsAppAccount
from app.services.meta_api import meta_api_service
from app.services.openwa_client import OpenWAError, openwa_client


class WhatsAppGatewayService:
    """Send through the provider selected on a tenant WhatsApp account."""

    async def send_text(
        self,
        account: WhatsAppAccount,
        *,
        to: str,
        text: str,
    ) -> dict[str, Any]:
        self._require_send_allowed(account)
        if account.provider == "openwa":
            if not account.provider_session_id:
                raise OpenWAError("OpenWA oturum kimliği eksik.")
            result = await openwa_client.send_text(account.provider_session_id, to, text)
            return {
                "provider": "openwa",
                "message_id": result.get("messageId"),
                "raw": result,
            }

        access_token = decrypt_token(account.access_token_encrypted)
        if not access_token or not account.phone_number_id:
            raise RuntimeError("Meta WhatsApp erişim bilgileri eksik.")
        result = await meta_api_service.send_text_message(
            access_token=access_token,
            phone_number_id=account.phone_number_id,
            to=to,
            text=text,
        )
        return {
            "provider": "meta_cloud",
            "message_id": result.get("messages", [{}])[0].get("id"),
            "raw": result,
        }

    async def send_template(
        self,
        account: WhatsAppAccount,
        *,
        to: str,
        template_name: str,
        language_code: str = "tr",
        components: list[dict] | None = None,
    ) -> dict[str, Any]:
        self._require_send_allowed(account)
        if account.provider == "openwa":
            raise OpenWAError(
                "OpenWA Meta şablonlarını desteklemez. Bu hesapta normal metin mesajı kullanın."
            )

        access_token = decrypt_token(account.access_token_encrypted)
        if not access_token or not account.phone_number_id:
            raise RuntimeError("Meta WhatsApp erişim bilgileri eksik.")
        result = await meta_api_service.send_template_message(
            access_token=access_token,
            phone_number_id=account.phone_number_id,
            to=to,
            template_name=template_name,
            language_code=language_code,
            components=components,
        )
        return {
            "provider": "meta_cloud",
            "message_id": result.get("messages", [{}])[0].get("id"),
            "raw": result,
        }

    async def send_document(
        self,
        account: WhatsAppAccount,
        *,
        to: str,
        link: str | None = None,
        media_id: str | None = None,
        content_bytes: bytes | None = None,
        mime_type: str = "application/octet-stream",
        filename: str | None = None,
        caption: str | None = None,
    ) -> dict[str, Any]:
        self._require_send_allowed(account)
        if account.provider == "openwa":
            if not account.provider_session_id:
                raise OpenWAError("OpenWA oturum kimliği eksik.")
            result = await openwa_client.send_document(
                account.provider_session_id,
                to,
                link=link,
                base64_data=base64.b64encode(content_bytes).decode() if content_bytes else None,
                mimetype=mime_type,
                filename=filename,
                caption=caption,
            )
            return {
                "provider": "openwa",
                "message_id": result.get("messageId"),
                "raw": result,
            }

        access_token = decrypt_token(account.access_token_encrypted)
        if not access_token or not account.phone_number_id:
            raise RuntimeError("Meta WhatsApp erişim bilgileri eksik.")
        if content_bytes:
            upload_result = await meta_api_service.upload_media(
                access_token=access_token,
                phone_number_id=account.phone_number_id,
                filename=filename or "document",
                content_bytes=content_bytes,
                mime_type=mime_type,
            )
            media_id = upload_result.get("id")
        result = await meta_api_service.send_document_message(
            access_token=access_token,
            phone_number_id=account.phone_number_id,
            to=to,
            media_id=media_id,
            link=link,
            filename=filename,
            caption=caption,
        )
        return {
            "provider": "meta_cloud",
            "message_id": result.get("messages", [{}])[0].get("id"),
            "raw": result,
        }

    async def send_media(
        self,
        account: WhatsAppAccount,
        *,
        to: str,
        media_type: str,
        content_bytes: bytes,
        mime_type: str,
        filename: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        if media_type == "catalog":
            return await self.send_document(
                account,
                to=to,
                content_bytes=content_bytes,
                mime_type=mime_type,
                filename=filename,
                caption=caption,
            )
        if media_type not in {"image", "video"}:
            raise RuntimeError("Desteklenmeyen WhatsApp medya türü.")

        self._require_send_allowed(account)
        if account.provider == "openwa":
            if not account.provider_session_id:
                raise OpenWAError("OpenWA oturum kimliği eksik.")
            result = await openwa_client.send_media(
                account.provider_session_id,
                to,
                media_type=media_type,
                base64_data=base64.b64encode(content_bytes).decode(),
                mimetype=mime_type,
                filename=filename,
                caption=caption,
            )
            return {
                "provider": "openwa",
                "message_id": result.get("messageId"),
                "raw": result,
            }

        access_token = decrypt_token(account.access_token_encrypted)
        if not access_token or not account.phone_number_id:
            raise RuntimeError("Meta WhatsApp erişim bilgileri eksik.")
        upload_result = await meta_api_service.upload_media(
            access_token=access_token,
            phone_number_id=account.phone_number_id,
            filename=filename,
            content_bytes=content_bytes,
            mime_type=mime_type,
        )
        result = await meta_api_service.send_media_message(
            access_token=access_token,
            phone_number_id=account.phone_number_id,
            to=to,
            media_type=media_type,
            media_id=upload_result["id"],
            caption=caption,
        )
        return {
            "provider": "meta_cloud",
            "message_id": result.get("messages", [{}])[0].get("id"),
            "raw": result,
        }

    @staticmethod
    def _require_send_allowed(account: WhatsAppAccount) -> None:
        key = f"whatsapp-send:{account.tenant_id}"
        if not whatsapp_send_minute_rate_limiter.allow(key):
            raise RuntimeError("Dakikalık WhatsApp gönderim limiti aşıldı.")
        if not whatsapp_send_hour_rate_limiter.allow(key):
            raise RuntimeError("Saatlik WhatsApp gönderim limiti aşıldı.")


whatsapp_gateway_service = WhatsAppGatewayService()
