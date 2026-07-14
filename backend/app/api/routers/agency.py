"""Agency client dashboard endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.tenant import Tenant
from app.models.user import User
from app.services.autopilot_service import AgencyService


router = APIRouter(prefix="/agency", tags=["Agency"])


class AgencyClientCreateRequest(BaseModel):
    client_tenant_id: UUID
    notes: str | None = Field(default=None, max_length=2000)


class AgencyClientUpdateRequest(BaseModel):
    status: str | None = Field(default=None, pattern="^(active|paused|archived)$")
    notes: str | None = Field(default=None, max_length=2000)


@router.get("/clients")
async def list_agency_clients(
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["agency:read"])),
) -> dict:
    _ = current_user
    return {"items": AgencyService(db).list_clients(current_tenant)}


@router.post("/clients", status_code=status.HTTP_201_CREATED)
async def create_agency_client(
    payload: AgencyClientCreateRequest,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["agency:write"])),
) -> dict:
    result = AgencyService(db).create_client_relationship(
        current_tenant,
        payload.client_tenant_id,
        current_user,
        notes=payload.notes,
    )
    if not result.get("client"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("detail", "Client eklenemedi"))
    return result


@router.get("/clients/{tenant_id}/health")
async def get_agency_client_health(
    tenant_id: UUID,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["agency:read"])),
) -> dict:
    _ = current_user
    payload = AgencyService(db).get_client_health(current_tenant, tenant_id)
    if not payload.get("found"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=payload.get("detail", "Client bulunamadı"))
    return payload


@router.patch("/clients/{relationship_id}")
async def update_agency_client(
    relationship_id: UUID,
    payload: AgencyClientUpdateRequest,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["agency:write"])),
) -> dict:
    _ = current_user
    result = AgencyService(db).update_client_relationship(
        current_tenant,
        relationship_id,
        status=payload.status,
        notes=payload.notes,
    )
    if not result.get("found"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("detail", "Client bulunamadı"))
    return result


@router.delete("/clients/{relationship_id}")
async def archive_agency_client(
    relationship_id: UUID,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["agency:write"])),
) -> dict:
    _ = current_user
    result = AgencyService(db).archive_client_relationship(current_tenant, relationship_id)
    if not result.get("found"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("detail", "Client bulunamadı"))
    return result
