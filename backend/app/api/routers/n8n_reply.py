import logging
import os
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

N8N_REPLY_BEARER_TOKEN = os.getenv("N8N_REPLY_BEARER_TOKEN")
if not N8N_REPLY_BEARER_TOKEN:
    raise RuntimeError(
        "FATAL: N8N_REPLY_BEARER_TOKEN is not set. "
        "Set it in the environment to enable /integrations/n8n/reply."
    )

router = APIRouter(prefix="/integrations/n8n", tags=["n8n Integrations"])


class N8NReplyIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    tenantHint: str
    replyText: str


def _verify_n8n_reply_bearer(authorization: Optional[str] = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    token = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(token, N8N_REPLY_BEARER_TOKEN):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@router.post("/reply")
async def n8n_reply(body: N8NReplyIn, _: None = Depends(_verify_n8n_reply_bearer)):
    reply_text_truncated = (body.replyText or "")[:500]
    logger.info(
        "n8n reply received tenantHint=%s from=%s replyText=%s",
        body.tenantHint,
        body.from_,
        reply_text_truncated,
    )
    return {"ok": True}

