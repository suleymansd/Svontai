"""Core assistant router (tool-aware chat)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tool_runner import (
    AssistantChatRequest,
    AssistantChatResponse,
    ToolRunRequest,
)
from app.services.tool_runner_service import ToolRunnerService


router = APIRouter(prefix="/assistant", tags=["Assistant"])


def _extract_tool_call(payload: AssistantChatRequest) -> tuple[str | None, str]:
    if payload.preferred_tool:
        return payload.preferred_tool.strip(), payload.message

    raw = payload.message.strip()
    if raw.lower().startswith("/tool "):
        remaining = raw[6:].strip()
        if not remaining:
            return None, payload.message
        parts = remaining.split(" ", 1)
        slug = parts[0].strip()
        text = parts[1].strip() if len(parts) > 1 else ""
        return slug, text

    return None, payload.message


@router.post("/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    payload: AssistantChatRequest,
    request: Request,
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> AssistantChatResponse:
    tool_slug, tool_text = _extract_tool_call(payload)
    request_id = payload.request_id or ""

    if not tool_slug:
        return AssistantChatResponse(
            requestId=request_id or "direct-response",
            mode="direct",
            message="Mesaj alındı. Tool çalıştırmak için `/tool <slug> <istek>` formatını kullanabilirsiniz.",
            toolResult=None,
        )

    service = ToolRunnerService(db)
    try:
        tool_result = await service.run_tool(
            tenant_id=current_tenant.id,
            user_id=current_user.id,
            payload=ToolRunRequest(
                requestId=payload.request_id,
                toolSlug=tool_slug,
                toolInput={"text": tool_text, "message": payload.message},
                context=payload.context,
            ),
            correlation_id=x_correlation_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        message = str(exc)
        if message == "Tool not found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
        if message == "Tool rate limit exceeded":
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=message)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    return AssistantChatResponse(
        requestId=tool_result.request_id,
        mode="tool",
        message="Tool çalıştırıldı." if tool_result.success else "Tool çalıştırılamadı.",
        toolResult=tool_result,
    )
