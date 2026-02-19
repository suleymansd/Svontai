"""
n8n integration helper endpoints.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.routers.n8n_reply import _verify_n8n_reply_bearer
from app.core.config import settings
from app.db.session import get_db
from app.models.automation import AutomationRunStatus
from app.core.n8n_security import create_n8n_jwt_token
from app.services.n8n_client import N8NClient


router = APIRouter(prefix="/integrations/n8n", tags=["n8n Dev (temp)"])
logger = logging.getLogger(__name__)


class N8NDevTokenRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: UUID = Field(alias="tenantId")


class N8NDevTokenResponse(BaseModel):
    token: str


class N8NTriggerTestRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: UUID = Field(alias="tenantId")
    from_: str = Field(alias="from")
    text: str


@router.post("/dev-token", response_model=N8NDevTokenResponse)
async def generate_n8n_dev_token(
    body: N8NDevTokenRequest,
    _: None = Depends(_verify_n8n_reply_bearer),
) -> N8NDevTokenResponse:
    token = create_n8n_jwt_token(str(body.tenant_id), expires_minutes=10)
    return N8NDevTokenResponse(token=token)


@router.post("/trigger-test")
async def trigger_n8n_test(
    body: N8NTriggerTestRequest,
    _: None = Depends(_verify_n8n_reply_bearer),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    client = N8NClient(db)
    tenant_id = body.tenant_id

    if not client.should_use_n8n(tenant_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="n8n is not enabled for this tenant",
        )

    workflow_id = client.get_workflow_id(tenant_id, channel="whatsapp")
    if not workflow_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No n8n workflow configured for tenant whatsapp channel",
        )

    webhook_url = f"{client.get_n8n_url(tenant_id)}{settings.N8N_WEBHOOK_PATH}/{workflow_id}"
    logger.info("n8n trigger-test final webhook_url=%s tenant_id=%s", webhook_url, tenant_id)

    message_id = f"trigger-test-{uuid4()}"
    run = await client.trigger_incoming_message(
        tenant_id=tenant_id,
        from_number=body.from_,
        to_number="trigger-test",
        text=body.text,
        message_id=message_id,
        timestamp=datetime.utcnow().isoformat(),
        channel="whatsapp",
        correlation_id=str(uuid4()),
        contact_name=None,
        raw_payload={"source": "trigger-test"},
        extra_data={"source": "trigger-test"},
    )

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="n8n trigger was not executed",
        )

    db.refresh(run)
    if run.status != AutomationRunStatus.SUCCESS.value:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"n8n call failed: {run.status}",
        )

    return {"ok": True}
