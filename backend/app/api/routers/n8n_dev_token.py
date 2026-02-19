"""
Development-only helper endpoints for n8n integration.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.routers.n8n_reply import _verify_n8n_reply_bearer
from app.core.n8n_security import create_n8n_jwt_token


router = APIRouter(prefix="/integrations/n8n", tags=["n8n Dev (temp)"])


class N8NDevTokenRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tenant_id: UUID = Field(alias="tenantId")


class N8NDevTokenResponse(BaseModel):
    token: str


@router.post("/dev-token", response_model=N8NDevTokenResponse)
async def generate_n8n_dev_token(
    body: N8NDevTokenRequest,
    _: None = Depends(_verify_n8n_reply_bearer),
) -> N8NDevTokenResponse:
    token = create_n8n_jwt_token(str(body.tenant_id), expires_minutes=10)
    return N8NDevTokenResponse(token=token)
