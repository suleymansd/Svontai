"""
Tenant Onboarding API router for managing setup wizard.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_current_tenant
from app.dependencies.permissions import require_permissions
from app.models.user import User
from app.models.tenant import Tenant
from app.services.tenant_onboarding_service import TenantOnboardingService


router = APIRouter(prefix="/onboarding/setup", tags=["onboarding"])


# Schemas
class StepResponse(BaseModel):
    key: str
    title: str
    description: str
    order: int
    required: bool
    completed: bool
    completed_at: str | None
    is_current: bool


class OnboardingStatusResponse(BaseModel):
    is_completed: bool
    completed_at: str | None
    current_step: str
    progress_percentage: int
    dismissed: bool
    steps: list[StepResponse]


class NextActionResponse(BaseModel):
    action: str | None
    message: str
    url: str


class CompleteStepRequest(BaseModel):
    step_key: str


# Endpoints
@router.get("/status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
):
    """Get current onboarding status."""
    service = TenantOnboardingService(db)
    return service.get_onboarding_status(tenant.id)


@router.post("/complete-step", response_model=OnboardingStatusResponse)
async def complete_onboarding_step(
    request: CompleteStepRequest,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
):
    """Mark an onboarding step as completed."""
    service = TenantOnboardingService(db)
    return service.complete_step(tenant.id, request.step_key)


@router.post("/dismiss", response_model=OnboardingStatusResponse)
async def dismiss_onboarding(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
):
    """Dismiss the onboarding wizard."""
    service = TenantOnboardingService(db)
    return service.dismiss_onboarding(tenant.id)


@router.post("/check-progress", response_model=OnboardingStatusResponse)
async def check_onboarding_progress(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
):
    """Auto-check and update onboarding progress based on current state."""
    service = TenantOnboardingService(db)
    return service.auto_check_progress(tenant.id)


@router.get("/next-action", response_model=NextActionResponse)
async def get_next_action(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
):
    """Get the next recommended action for onboarding."""
    service = TenantOnboardingService(db)
    return service.get_next_action(tenant.id)
