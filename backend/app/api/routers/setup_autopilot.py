"""Autopilot setup endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.tenant import Tenant
from app.models.user import User
from app.services.autopilot_service import AutopilotService
from app.services.system_verification_service import SystemVerificationService


router = APIRouter(prefix="/setup/autopilot", tags=["Autopilot Setup"])


@router.get("/status")
async def get_autopilot_status(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"])),
) -> dict:
    _ = current_user
    return AutopilotService(db).status(current_tenant)


@router.post("/run")
async def run_autopilot(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"])),
) -> dict:
    return AutopilotService(db).run(current_tenant, current_user)


@router.post("/verify")
async def verify_autopilot_system(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"])),
) -> dict:
    """Run no-charge, non-destructive production checks for this tenant."""
    return SystemVerificationService(db).run(current_tenant, current_user)
