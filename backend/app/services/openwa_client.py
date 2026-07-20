"""HTTP client for the OpenWA QR-based WhatsApp gateway."""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import settings


class OpenWAError(RuntimeError):
    """A sanitized OpenWA integration error."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class OpenWAClient:
    """Small provider client matching OpenWA's committed OpenAPI contract."""

    def __init__(self) -> None:
        self.base_url = settings.OPENWA_BASE_URL.rstrip("/")
        self.api_key = settings.OPENWA_API_KEY.strip()
        self.timeout = settings.OPENWA_TIMEOUT_SECONDS

    @property
    def configured(self) -> bool:
        return bool(
            settings.OPENWA_ENABLED
            and self.base_url
            and self.api_key
            and settings.OPENWA_WEBHOOK_SECRET.strip()
        )

    def _headers(self) -> dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        allow_statuses: set[int] | None = None,
    ) -> Any:
        if not self.configured:
            raise OpenWAError("OpenWA yapılandırması hazır değil.")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=self._headers(),
                    json=json,
                )
        except httpx.RequestError as exc:
            raise OpenWAError("OpenWA servisine ulaşılamadı.") from exc

        if allow_statuses and response.status_code in allow_statuses:
            return None

        if response.is_error:
            detail = ""
            try:
                payload = response.json()
                detail = str(payload.get("message") or payload.get("error") or "")
            except (ValueError, AttributeError):
                detail = ""
            suffix = f" {detail[:240]}" if detail else ""
            raise OpenWAError(
                f"OpenWA isteği başarısız oldu (HTTP {response.status_code}).{suffix}",
                status_code=response.status_code,
            )

        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise OpenWAError("OpenWA geçersiz JSON yanıtı döndürdü.") from exc

    async def health(self) -> dict[str, Any]:
        result = await self._request("GET", "/api/health/ready")
        return result if isinstance(result, dict) else {"status": "unknown"}

    async def list_sessions(self) -> list[dict[str, Any]]:
        result = await self._request("GET", "/api/sessions")
        return result if isinstance(result, list) else []

    async def get_session(self, session_id: str) -> dict[str, Any]:
        result = await self._request("GET", f"/api/sessions/{session_id}")
        return result if isinstance(result, dict) else {}

    async def create_or_get_session(self, name: str) -> dict[str, Any]:
        try:
            result = await self._request(
                "POST",
                "/api/sessions",
                json={"name": name, "config": {"autoReconnect": True}},
            )
            return result if isinstance(result, dict) else {}
        except OpenWAError as exc:
            if exc.status_code != 409:
                raise

        sessions = await self.list_sessions()
        existing = next((item for item in sessions if item.get("name") == name), None)
        if not existing:
            raise OpenWAError("Mevcut OpenWA oturumu bulunamadı.")
        return existing

    async def start_session(self, session_id: str) -> dict[str, Any]:
        try:
            result = await self._request("POST", f"/api/sessions/{session_id}/start")
            return result if isinstance(result, dict) else {}
        except OpenWAError as exc:
            if exc.status_code != 400:
                raise
            return await self.get_session(session_id)

    async def get_qr(self, session_id: str) -> dict[str, Any]:
        result = await self._request("GET", f"/api/sessions/{session_id}/qr")
        return result if isinstance(result, dict) else {}

    async def get_contact(self, session_id: str, contact_id: str) -> dict[str, Any]:
        """Return the best contact details cached by the tenant's WhatsApp session."""
        safe_contact_id = quote(contact_id.strip(), safe="")
        if not safe_contact_id:
            return {}
        result = await self._request(
            "GET",
            f"/api/sessions/{session_id}/contacts/{safe_contact_id}",
        )
        return result if isinstance(result, dict) else {}

    async def ensure_webhook(self, session_id: str, url: str) -> dict[str, Any]:
        result = await self._request("GET", f"/api/sessions/{session_id}/webhooks")
        webhooks = result if isinstance(result, list) else []
        existing = next((item for item in webhooks if item.get("url") == url), None)
        webhook_payload = {
            "url": url,
            "events": [
                "message.received",
                "session.status",
                "session.authenticated",
                "session.disconnected",
            ],
            "secret": self.webhook_secret(session_id),
            "retryCount": 3,
        }
        if existing:
            updated = await self._request(
                "PUT",
                f"/api/sessions/{session_id}/webhooks/{existing['id']}",
                json={**webhook_payload, "active": True},
            )
            return updated if isinstance(updated, dict) else existing

        created = await self._request(
            "POST",
            f"/api/sessions/{session_id}/webhooks",
            json=webhook_payload,
        )
        return created if isinstance(created, dict) else {}

    async def delete_session(self, session_id: str) -> None:
        await self._request(
            "DELETE",
            f"/api/sessions/{session_id}",
            allow_statuses={404},
        )

    async def send_text(self, session_id: str, to: str, text: str) -> dict[str, Any]:
        result = await self._request(
            "POST",
            f"/api/sessions/{session_id}/messages/send-text",
            json={"chatId": self.chat_id(to), "text": text},
        )
        return result if isinstance(result, dict) else {}

    async def send_document(
        self,
        session_id: str,
        to: str,
        *,
        link: str | None = None,
        base64_data: str | None = None,
        mimetype: str | None = None,
        filename: str | None = None,
        caption: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"chatId": self.chat_id(to)}
        if link:
            payload["url"] = link
        if base64_data:
            payload["base64"] = base64_data
            payload["mimetype"] = mimetype or "application/octet-stream"
        if not link and not base64_data:
            raise OpenWAError("Belge bağlantısı veya base64 içeriği gerekli.")
        if filename:
            payload["filename"] = filename
        if caption:
            payload["caption"] = caption
        result = await self._request(
            "POST",
            f"/api/sessions/{session_id}/messages/send-document",
            json=payload,
        )
        return result if isinstance(result, dict) else {}

    @staticmethod
    def chat_id(phone: str) -> str:
        if phone.endswith(("@c.us", "@s.whatsapp.net", "@g.us", "@lid")):
            return phone
        digits = re.sub(r"\D", "", phone)
        if not digits:
            raise OpenWAError("Geçerli bir WhatsApp numarası gerekli.")
        return f"{digits}@c.us"

    @staticmethod
    def phone_from_jid(value: str | None) -> str:
        if not value:
            return ""
        return value.split("@", 1)[0]

    @staticmethod
    def webhook_secret(session_id: str) -> str:
        master_secret = settings.OPENWA_WEBHOOK_SECRET.strip()
        if not master_secret or not session_id:
            return ""
        return hmac.new(
            master_secret.encode(),
            f"openwa-webhook:{session_id}".encode(),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def verify_signature(body: bytes, signature: str | None, session_id: str) -> bool:
        secret = OpenWAClient.webhook_secret(session_id)
        if not secret or not signature or not signature.startswith("sha256="):
            return False
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature[7:], expected)


openwa_client = OpenWAClient()
