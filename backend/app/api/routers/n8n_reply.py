import logging
import os
import secrets
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.routers.n8n_tools import _normalize_phone
from app.core.encryption import decrypt_token
from app.db.session import get_db
from app.models.tenant import Tenant
from app.models.whatsapp_account import WhatsAppAccount
from app.services.meta_api import meta_api_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/n8n", tags=["n8n Integrations"])


class N8NReplyIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    tenantHint: str
    replyText: str


def _verify_n8n_reply_bearer(authorization: Optional[str] = Header(default=None)) -> None:
    expected_token = os.getenv("N8N_REPLY_BEARER_TOKEN")
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="N8N_REPLY_BEARER_TOKEN missing",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    token = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(token, expected_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@router.post("/reply")
async def n8n_reply(
    body: N8NReplyIn,
    _: None = Depends(_verify_n8n_reply_bearer),
    db: Session = Depends(get_db),
):
    reply_text_truncated = (body.replyText or "")[:500]
    logger.info(
        "n8n reply received tenantHint=%s from=%s replyText=%s",
        body.tenantHint,
        body.from_,
        reply_text_truncated,
    )

    tenant_hint = (body.tenantHint or "").strip()
    tenant: Tenant | None = None
    if not tenant_hint:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tenantHint is required")

    try:
        tenant_id = UUID(tenant_hint)
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    except ValueError:
        tenant = db.query(Tenant).filter(Tenant.slug == tenant_hint).first()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    normalized_from = _normalize_phone(body.from_) or body.from_
    to_number = (normalized_from or "").lstrip("+")
    if not to_number or not to_number.isdigit():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid from number")

    account = db.query(WhatsAppAccount).filter(
        WhatsAppAccount.tenant_id == tenant.id,
        WhatsAppAccount.is_active.is_(True),
    ).first()
    if not account or not account.phone_number_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Active WhatsApp account not found for tenant",
        )

    access_token = decrypt_token(account.access_token_encrypted) if account.access_token_encrypted else None
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WhatsApp access token not available",
        )

    try:
        await meta_api_service.send_text_message(
            access_token=access_token,
            phone_number_id=account.phone_number_id,
            to=to_number,
            text=body.replyText,
        )
        return {"ok": True, "sent": True}
    except Exception as exc:
        logger.warning("n8n reply WhatsApp send failed: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"ok": False, "sent": False, "error": str(exc)[:200]},
        )
