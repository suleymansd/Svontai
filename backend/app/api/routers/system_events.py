"""System events API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_current_tenant
from app.dependencies.permissions import require_permissions
from app.models.system_event import SystemEvent
from app.schemas.system_event import SystemEventResponse
from app.models.user import User
from app.models.tenant import Tenant

router = APIRouter(prefix="/system-events", tags=["system-events"])


@router.get("", response_model=list[SystemEventResponse])
async def list_system_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    level: str | None = None,
    source: str | None = None,
    code: str | None = None,
    tenant_id: str | None = None,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    _: None = Depends(require_permissions(["audit:read"])),
    db: Session = Depends(get_db),
):
    query = db.query(SystemEvent)
    if current_user.is_admin:
        if tenant_id:
            query = query.filter(SystemEvent.tenant_id == tenant_id)
    else:
        query = query.filter(SystemEvent.tenant_id == str(current_tenant.id))
    if level:
        query = query.filter(SystemEvent.level == level)
    if source:
        query = query.filter(SystemEvent.source == source)
    if code:
        query = query.filter(SystemEvent.code == code)
    return query.order_by(SystemEvent.created_at.desc()).offset(skip).limit(limit).all()
