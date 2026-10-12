"""Admin-issued links that open a separate Premium evaluation workspace."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.routers.admin import require_admin
from app.api.routers.auth import _require_allowed_refresh_origin, _set_refresh_cookie
from app.core.rate_limit import client_ip, rate_limit_key, require_rate_limit
from app.core.security import hash_token
from app.core.time import utc_now_naive
from app.db.session import get_db
from app.models.demo_access import DemoAccess
from app.models.user import User
from app.schemas.auth import AccessTokenResponse
from app.services.demo_access_service import DemoAccessService, demo_login_limiter, ensure_demo_active

admin_router = APIRouter(prefix="/admin/demo-access", tags=["admin"])
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


class DemoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=160)
    days: int = Field(default=14, ge=1, le=30)


class DemoLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class DemoItem(BaseModel):
    id: UUID
    name: str
    tenant_id: UUID
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None
    visit_count: int
    status: str


class DemoLink(DemoItem):
    url: str


def item(demo: DemoAccess) -> dict:
    state = "revoked" if demo.revoked_at else "expired" if demo.expires_at <= utc_now_naive() else "active"
    return {key: getattr(demo, key) for key in DemoItem.model_fields if key != "status"} | {"status": state}


def find(db: Session, demo_id: UUID) -> DemoAccess:
    demo = db.query(DemoAccess).filter(DemoAccess.id == demo_id).with_for_update().first()
    if demo is None:
        raise HTTPException(404, detail="Özel erişim bulunamadı.")
    return demo


@admin_router.get("", response_model=list[DemoItem])
def list_links(response: Response, db: Session = Depends(get_db), admin: User = Depends(require_admin), limit: int = Query(100, ge=1, le=200)):
    response.headers["Cache-Control"] = "no-store"
    return [item(demo) for demo in db.query(DemoAccess).order_by(DemoAccess.created_at.desc()).limit(limit).all()]


@admin_router.post("", response_model=DemoLink, status_code=201)
def create_link(payload: DemoCreate, response: Response, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    service = DemoAccessService(db)
    demo, token = service.create(payload.name, payload.days, admin)
    response.headers["Cache-Control"] = "no-store"
    return {**item(demo), "url": service.url(token)}


@admin_router.post("/{demo_id}/rotate", response_model=DemoLink)
def rotate_link(demo_id: UUID, response: Response, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    demo = find(db, demo_id)
    ensure_demo_active(demo)
    service = DemoAccessService(db)
    token = service.new_token()
    demo.token_hash = hash_token(token)
    service.revoke_sessions(demo)
    service.audit(demo, admin.id, "demo_access.rotated")
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {**item(demo), "url": service.url(token)}


@admin_router.delete("/{demo_id}", status_code=204)
def revoke_link(demo_id: UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    demo = find(db, demo_id)
    if not demo.revoked_at:
        demo.revoked_at = utc_now_naive()
        service = DemoAccessService(db)
        service.revoke_sessions(demo)
        service.audit(demo, admin.id, "demo_access.revoked")
        db.commit()


@auth_router.post("/demo-login", response_model=AccessTokenResponse)
def demo_login(payload: DemoLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    _require_allowed_refresh_origin(request)
    require_rate_limit(demo_login_limiter, rate_limit_key(request, "demo-login"))
    require_rate_limit(demo_login_limiter, f"link:{hash_token(payload.token)}")
    access, refresh = DemoAccessService(db).enter(payload.token, client_ip(request), request.headers.get("user-agent", ""))
    _set_refresh_cookie(response, refresh)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return AccessTokenResponse(access_token=access)
