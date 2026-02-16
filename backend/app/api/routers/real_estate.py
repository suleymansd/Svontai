"""
Real Estate Pack API router.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote_plus
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import settings
from app.dependencies.auth import get_current_tenant, get_current_user
from app.dependencies.permissions import require_permissions
from app.models.lead import Lead
from app.models.real_estate import (
    RealEstateGoogleCalendarIntegration,
    RealEstateListing,
    RealEstatePackSettings,
    RealEstateTemplateRegistry,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.services.audit_log_service import AuditLogService
from app.services.google_calendar_service import GoogleCalendarError, GoogleCalendarService
from app.services.real_estate_service import RealEstateService


router = APIRouter(prefix="/real-estate", tags=["Real Estate Pack"])


class RealEstateSettingsResponse(BaseModel):
    enabled: bool
    persona: str
    lead_limit_monthly: int
    pdf_limit_monthly: int
    followup_limit_monthly: int
    followup_days: int
    followup_attempts: int
    question_flow_buyer: dict
    question_flow_seller: dict
    listings_source: dict
    manual_availability: list
    google_calendar_enabled: bool
    google_calendar_email: str | None
    report_logo_url: str | None
    report_brand_color: str
    report_footer: str | None


class RealEstateSettingsUpdate(BaseModel):
    enabled: bool | None = None
    persona: str | None = Field(default=None, pattern="^(luxury|pro|warm)$")
    lead_limit_monthly: int | None = Field(default=None, ge=1)
    pdf_limit_monthly: int | None = Field(default=None, ge=1)
    followup_limit_monthly: int | None = Field(default=None, ge=1)
    followup_days: int | None = Field(default=None, ge=1, le=30)
    followup_attempts: int | None = Field(default=None, ge=1, le=5)
    question_flow_buyer: dict | None = None
    question_flow_seller: dict | None = None
    listings_source: dict | None = None
    manual_availability: list | None = None
    google_calendar_enabled: bool | None = None
    google_calendar_email: str | None = None
    report_logo_url: str | None = None
    report_brand_color: str | None = None
    report_footer: str | None = None


class ListingCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str | None = None
    sale_rent: str = Field(pattern="^(sale|rent)$")
    property_type: str = Field(min_length=2, max_length=30)
    location_text: str = Field(min_length=2, max_length=255)
    lat: float | None = None
    lng: float | None = None
    price: int = Field(ge=1)
    currency: str = Field(default="TRY", max_length=6)
    m2: int | None = Field(default=None, ge=1)
    rooms: str | None = Field(default=None, max_length=20)
    features: dict = Field(default_factory=dict)
    media: list = Field(default_factory=list)
    url: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class ListingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = None
    sale_rent: str | None = Field(default=None, pattern="^(sale|rent)$")
    property_type: str | None = Field(default=None, min_length=2, max_length=30)
    location_text: str | None = Field(default=None, min_length=2, max_length=255)
    lat: float | None = None
    lng: float | None = None
    price: int | None = Field(default=None, ge=1)
    currency: str | None = Field(default=None, max_length=6)
    m2: int | None = Field(default=None, ge=1)
    rooms: str | None = Field(default=None, max_length=20)
    features: dict | None = None
    media: list | None = None
    url: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class ListingResponse(BaseModel):
    id: str
    title: str
    description: str | None
    sale_rent: str
    property_type: str
    location_text: str
    lat: float | None
    lng: float | None
    price: int
    currency: str
    m2: int | None
    rooms: str | None
    features: dict
    media: list
    url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TemplateCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    category: str = Field(min_length=2, max_length=50)
    language: str = Field(default="tr", max_length=10)
    meta_template_id: str | None = Field(default=None, max_length=120)
    variables_schema: dict = Field(default_factory=dict)
    status: str = Field(default="draft", max_length=20)
    content_preview: str | None = None
    is_approved: bool = False


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=120)
    category: str | None = Field(default=None, min_length=2, max_length=50)
    language: str | None = Field(default=None, max_length=10)
    meta_template_id: str | None = Field(default=None, max_length=120)
    variables_schema: dict | None = None
    status: str | None = Field(default=None, max_length=20)
    content_preview: str | None = None
    is_approved: bool | None = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    category: str
    language: str
    meta_template_id: str | None
    variables_schema: dict
    status: str
    content_preview: str | None
    is_approved: bool
    created_at: datetime
    updated_at: datetime


class SuggestListingResponse(BaseModel):
    lead_id: str
    count: int
    listings: list[ListingResponse]


class BookAppointmentRequest(BaseModel):
    lead_id: UUID
    agent_id: UUID | None = None
    listing_id: UUID | None = None
    start_at: datetime
    end_at: datetime | None = None
    meeting_mode: str = Field(default="in_person", max_length=20)
    notes: str | None = None


class FollowupRunResponse(BaseModel):
    pending: int
    sent: int
    skipped: int
    failed: int


class GoogleCalendarStartResponse(BaseModel):
    auth_url: str
    state: str


class GoogleCalendarStatusResponse(BaseModel):
    connected: bool
    status: str
    calendar_id: str | None


class GoogleCalendarDiagnosticsResponse(BaseModel):
    environment: str
    backend_url: str
    webhook_public_url: str
    google_client_id_set: bool
    google_client_secret_set: bool
    google_redirect_uri: str
    expected_redirect_uri: str
    checks: list[dict]
    issues: list[str]
    hints: list[str]
    auth_url_preview: str
    live_probe: dict | None = None


class ListingEventCreate(BaseModel):
    listing_id: UUID
    event: str = Field(pattern="^(sent|clicked|saved|ignored|viewed|offer)$")
    meta_json: dict | None = None


class SuggestedListingWithReason(BaseModel):
    listing: ListingResponse
    reasons: list[str]


class ListingSummaryPdfRequest(BaseModel):
    listing_ids: list[UUID] = Field(min_length=1)
    lead_id: UUID | None = None
    send_whatsapp: bool = False


class ListingSummaryPdfResponse(BaseModel):
    filename: str
    item_count: int
    whatsapp_sent: bool
    media_id: str | None = None
    summary: dict


class GoogleSheetsSyncRequest(BaseModel):
    sheet_url: str | None = None
    gid: str | None = None
    csv_url: str | None = None
    mapping: dict[str, str] = Field(default_factory=dict)
    deactivate_missing: bool = False
    save_to_settings: bool = True


class RemaxSyncRequest(BaseModel):
    endpoint_url: str | None = None
    response_path: str = "data.listings"
    auth_header: str = "Authorization"
    auth_scheme: str = "Bearer"
    api_key: str | None = None
    mapping: dict[str, str] = Field(default_factory=dict)
    deactivate_missing: bool = False
    save_to_settings: bool = True


class AvailableSlotResponse(BaseModel):
    start_at: str
    end_at: str


def _settings_to_response(settings: RealEstatePackSettings) -> RealEstateSettingsResponse:
    listing_source = dict(settings.listings_source or {})
    remax_cfg = listing_source.get("remax_connector")
    if isinstance(remax_cfg, dict):
        remax_safe = dict(remax_cfg)
        remax_safe.pop("api_key_encrypted", None)
        remax_safe.pop("api_key", None)
        listing_source["remax_connector"] = remax_safe

    return RealEstateSettingsResponse(
        enabled=settings.enabled,
        persona=settings.persona,
        lead_limit_monthly=settings.lead_limit_monthly,
        pdf_limit_monthly=settings.pdf_limit_monthly,
        followup_limit_monthly=settings.followup_limit_monthly,
        followup_days=settings.followup_days,
        followup_attempts=settings.followup_attempts,
        question_flow_buyer=settings.question_flow_buyer or {},
        question_flow_seller=settings.question_flow_seller or {},
        listings_source=listing_source,
        manual_availability=settings.manual_availability or [],
        google_calendar_enabled=settings.google_calendar_enabled,
        google_calendar_email=settings.google_calendar_email,
        report_logo_url=settings.report_logo_url,
        report_brand_color=settings.report_brand_color,
        report_footer=settings.report_footer,
    )


def _listing_to_response(row: RealEstateListing) -> ListingResponse:
    return ListingResponse(
        id=str(row.id),
        title=row.title,
        description=row.description,
        sale_rent=row.sale_rent,
        property_type=row.property_type,
        location_text=row.location_text,
        lat=row.lat,
        lng=row.lng,
        price=row.price,
        currency=row.currency,
        m2=row.m2,
        rooms=row.rooms,
        features=row.features or {},
        media=row.media or [],
        url=row.url,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _template_to_response(row: RealEstateTemplateRegistry) -> TemplateResponse:
    return TemplateResponse(
        id=str(row.id),
        name=row.name,
        category=row.category,
        language=row.language,
        meta_template_id=row.meta_template_id,
        variables_schema=row.variables_schema or {},
        status=row.status,
        content_preview=row.content_preview,
        is_approved=row.is_approved,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/settings", response_model=RealEstateSettingsResponse)
async def get_real_estate_settings(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> RealEstateSettingsResponse:
    service = RealEstateService(db)
    settings = service.get_or_create_settings(current_tenant.id)
    return _settings_to_response(settings)


@router.put("/settings", response_model=RealEstateSettingsResponse)
async def update_real_estate_settings(
    payload: RealEstateSettingsUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
) -> RealEstateSettingsResponse:
    service = RealEstateService(db)
    settings = service.upsert_settings(
        current_tenant.id,
        payload.model_dump(exclude_unset=True)
    )
    AuditLogService(db).log(
        action="real_estate.settings.update",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="real_estate_pack",
        resource_id=str(current_tenant.id),
        payload=payload.model_dump(exclude_unset=True),
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )
    return _settings_to_response(settings)


@router.get("/listings", response_model=list[ListingResponse])
async def list_real_estate_listings(
    search: str | None = None,
    sale_rent: str | None = Query(default=None, pattern="^(sale|rent)$"),
    active_only: bool = True,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> list[ListingResponse]:
    query = db.query(RealEstateListing).filter(
        RealEstateListing.tenant_id == current_tenant.id
    )
    if active_only:
        query = query.filter(RealEstateListing.is_active.is_(True))
    if sale_rent:
        query = query.filter(RealEstateListing.sale_rent == sale_rent)
    if search:
        query = query.filter(
            RealEstateListing.title.ilike(f"%{search}%")
            | RealEstateListing.location_text.ilike(f"%{search}%")
        )
    rows = query.order_by(RealEstateListing.created_at.desc()).all()
    return [_listing_to_response(row) for row in rows]


@router.post("/listings", response_model=ListingResponse, status_code=status.HTTP_201_CREATED)
async def create_real_estate_listing(
    payload: ListingCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
) -> ListingResponse:
    row = RealEstateListing(
        tenant_id=current_tenant.id,
        created_by=current_user.id,
        **payload.model_dump()
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    AuditLogService(db).log(
        action="real_estate.listing.create",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="real_estate_listing",
        resource_id=str(row.id),
        payload={"title": row.title, "sale_rent": row.sale_rent},
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )
    return _listing_to_response(row)


@router.patch("/listings/{listing_id}", response_model=ListingResponse)
async def update_real_estate_listing(
    listing_id: UUID,
    payload: ListingUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
) -> ListingResponse:
    row = db.query(RealEstateListing).filter(
        RealEstateListing.id == listing_id,
        RealEstateListing.tenant_id == current_tenant.id
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İlan bulunamadı")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    AuditLogService(db).log(
        action="real_estate.listing.update",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="real_estate_listing",
        resource_id=str(row.id),
        payload=updates,
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )
    return _listing_to_response(row)


@router.delete("/listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_real_estate_listing(
    listing_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
) -> None:
    row = db.query(RealEstateListing).filter(
        RealEstateListing.id == listing_id,
        RealEstateListing.tenant_id == current_tenant.id
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İlan bulunamadı")

    db.delete(row)
    db.commit()
    AuditLogService(db).log(
        action="real_estate.listing.delete",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="real_estate_listing",
        resource_id=str(listing_id),
        payload={"title": row.title},
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )


@router.post("/listings/import/csv", response_model=dict)
async def import_real_estate_listings_csv(
    file: UploadFile = File(...),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
) -> dict[str, Any]:
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))

    imported = 0
    skipped = 0
    for row in reader:
        title = (row.get("title") or "").strip()
        location_text = (row.get("location_text") or "").strip()
        sale_rent = (row.get("sale_rent") or "sale").strip().lower()
        property_type = (row.get("property_type") or "daire").strip().lower()
        try:
            price = int(float((row.get("price") or "0").replace(",", ".")))
        except ValueError:
            price = 0

        if not title or not location_text or sale_rent not in {"sale", "rent"} or price <= 0:
            skipped += 1
            continue

        listing = RealEstateListing(
            tenant_id=current_tenant.id,
            created_by=current_user.id,
            title=title,
            description=(row.get("description") or "").strip() or None,
            sale_rent=sale_rent,
            property_type=property_type,
            location_text=location_text,
            price=price,
            currency=(row.get("currency") or "TRY").strip() or "TRY",
            m2=int(row["m2"]) if row.get("m2") and str(row.get("m2")).isdigit() else None,
            rooms=(row.get("rooms") or "").strip() or None,
            url=(row.get("url") or "").strip() or None,
            features={},
            media=[],
            is_active=True,
        )
        db.add(listing)
        imported += 1

    db.commit()
    AuditLogService(db).log(
        action="real_estate.listing.import_csv",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="real_estate_listing",
        resource_id=str(current_tenant.id),
        payload={"imported": imported, "skipped": skipped, "filename": file.filename},
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )
    return {"imported": imported, "skipped": skipped}


@router.post("/listings/sync/google-sheets", response_model=dict)
async def sync_real_estate_listings_google_sheets(
    payload: GoogleSheetsSyncRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
) -> dict[str, Any]:
    service = RealEstateService(db)
    try:
        result = service.sync_listings_from_google_sheets(
            tenant_id=current_tenant.id,
            user_id=current_user.id,
            config=payload.model_dump(exclude_none=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Google Sheets sync başarısız: {exc}")

    AuditLogService(db).log(
        action="real_estate.listing.sync_google_sheets",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="real_estate_listing",
        resource_id=str(current_tenant.id),
        payload=result,
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )
    return result


@router.post("/listings/sync/remax", response_model=dict)
async def sync_real_estate_listings_remax(
    payload: RemaxSyncRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
) -> dict[str, Any]:
    service = RealEstateService(db)
    try:
        result = service.sync_listings_from_remax_connector(
            tenant_id=current_tenant.id,
            user_id=current_user.id,
            config=payload.model_dump(exclude_none=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Remax sync başarısız: {exc}")

    AuditLogService(db).log(
        action="real_estate.listing.sync_remax",
        tenant_id=str(current_tenant.id),
        user_id=str(current_user.id),
        resource_type="real_estate_listing",
        resource_id=str(current_tenant.id),
        payload=result,
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("User-Agent") if request else None
    )
    return result


@router.get("/templates", response_model=list[TemplateResponse])
async def list_real_estate_templates(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> list[TemplateResponse]:
    service = RealEstateService(db)
    service.ensure_default_templates(current_tenant.id)
    rows = db.query(RealEstateTemplateRegistry).filter(
        RealEstateTemplateRegistry.tenant_id == current_tenant.id
    ).order_by(RealEstateTemplateRegistry.created_at.desc()).all()
    return [_template_to_response(row) for row in rows]


@router.post("/templates", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_real_estate_template(
    payload: TemplateCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
) -> TemplateResponse:
    row = RealEstateTemplateRegistry(
        tenant_id=current_tenant.id,
        **payload.model_dump()
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _template_to_response(row)


@router.patch("/templates/{template_id}", response_model=TemplateResponse)
async def update_real_estate_template(
    template_id: UUID,
    payload: TemplateUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
) -> TemplateResponse:
    row = db.query(RealEstateTemplateRegistry).filter(
        RealEstateTemplateRegistry.id == template_id,
        RealEstateTemplateRegistry.tenant_id == current_tenant.id
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template bulunamadı")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return _template_to_response(row)


@router.post("/leads/{lead_id}/suggest-listings", response_model=SuggestListingResponse)
async def suggest_listings_for_lead(
    lead_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> SuggestListingResponse:
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.tenant_id == current_tenant.id
    ).first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead bulunamadı")

    service = RealEstateService(db)
    listings = service.suggest_listings_for_lead(current_tenant.id, lead_id)
    return SuggestListingResponse(
        lead_id=str(lead_id),
        count=len(listings),
        listings=[_listing_to_response(item) for item in listings]
    )


@router.get("/leads/{lead_id}/ai-suggested-listings", response_model=list[SuggestedListingWithReason])
async def ai_suggested_listings_for_lead(
    lead_id: UUID,
    limit: int = Query(default=3, ge=1, le=10),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> list[SuggestedListingWithReason]:
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.tenant_id == current_tenant.id
    ).first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead bulunamadı")

    service = RealEstateService(db)
    results = service.suggest_listings_with_reasons(current_tenant.id, lead_id, limit=limit)
    return [
        SuggestedListingWithReason(
            listing=_listing_to_response(item["listing"]),
            reasons=item["reasons"],
        )
        for item in results
    ]


@router.post("/leads/{lead_id}/listing-events", response_model=dict, status_code=status.HTTP_201_CREATED)
async def record_listing_event(
    lead_id: UUID,
    payload: ListingEventCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
) -> dict[str, Any]:
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.tenant_id == current_tenant.id
    ).first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead bulunamadı")
    listing = db.query(RealEstateListing).filter(
        RealEstateListing.id == payload.listing_id,
        RealEstateListing.tenant_id == current_tenant.id,
    ).first()
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İlan bulunamadı")

    row = RealEstateService(db).record_listing_event(
        tenant_id=current_tenant.id,
        lead_id=lead_id,
        listing_id=payload.listing_id,
        event=payload.event,
        meta_json=payload.meta_json,
    )
    return {"id": str(row.id), "event": row.event}


@router.post("/appointments/book", response_model=dict)
async def book_real_estate_appointment(
    payload: BookAppointmentRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
) -> dict[str, Any]:
    end_at = payload.end_at or (payload.start_at + timedelta(minutes=60))
    service = RealEstateService(db)
    appointment = service.book_appointment(
        tenant_id=current_tenant.id,
        lead_id=payload.lead_id,
        agent_id=payload.agent_id,
        listing_id=payload.listing_id,
        start_at=payload.start_at,
        end_at=end_at,
        meeting_mode=payload.meeting_mode,
        notes=payload.notes,
    )
    return {
        "id": str(appointment.id),
        "status": appointment.status,
        "start_at": appointment.start_at.isoformat(),
        "end_at": appointment.end_at.isoformat(),
    }


@router.get("/appointments/available-slots", response_model=list[AvailableSlotResponse])
async def get_available_appointment_slots(
    agent_id: UUID,
    start_at: datetime = Query(...),
    end_at: datetime = Query(...),
    duration_minutes: int = Query(default=60, ge=15, le=180),
    step_minutes: int = Query(default=30, ge=15, le=120),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> list[AvailableSlotResponse]:
    if end_at <= start_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_at start_at değerinden büyük olmalı")

    slots = RealEstateService(db).get_available_slots(
        tenant_id=current_tenant.id,
        agent_id=agent_id,
        start_at=start_at,
        end_at=end_at,
        duration_minutes=duration_minutes,
        step_minutes=step_minutes,
    )
    return [AvailableSlotResponse(**item) for item in slots]


@router.post("/followups/run", response_model=FollowupRunResponse)
async def run_followups(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
) -> FollowupRunResponse:
    service = RealEstateService(db)
    result = await service.run_followups(current_tenant.id)
    return FollowupRunResponse(**result)


@router.get("/analytics/weekly", response_model=dict)
async def get_weekly_real_estate_analytics(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> dict[str, Any]:
    service = RealEstateService(db)
    return service.get_weekly_metrics(current_tenant.id)


@router.get("/agents", response_model=list[dict])
async def list_real_estate_agents(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> list[dict[str, Any]]:
    return RealEstateService(db).list_agents(current_tenant.id)


@router.get("/calendar/google/start", response_model=GoogleCalendarStartResponse)
async def start_google_calendar_oauth(
    agent_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
) -> GoogleCalendarStartResponse:
    resolved_agent_id = agent_id or current_user.id
    service = GoogleCalendarService(db)
    try:
        data = service.get_oauth_start(current_tenant.id, resolved_agent_id)
    except GoogleCalendarError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return GoogleCalendarStartResponse(**data)


@router.get("/calendar/google/callback")
async def google_calendar_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    service = GoogleCalendarService(db)
    frontend_redirect_success = f"{(settings.FRONTEND_URL or '').rstrip('/')}/dashboard/tools/tool-real-estate-pack?google_calendar=success"
    frontend_redirect_error_base = f"{(settings.FRONTEND_URL or '').rstrip('/')}/dashboard/tools/tool-real-estate-pack?google_calendar=error"
    try:
        service.process_oauth_callback(code=code, state=state)
        success_payload = json.dumps({"type": "GOOGLE_CALENDAR_CONNECTED", "success": True})
        redirect_url_js = json.dumps(frontend_redirect_success)
        return HTMLResponse(
            content="""
            <html>
            <body>
                <script>
                    if (window.opener) {
                        window.opener.postMessage(""" + success_payload + """, '*');
                        window.close();
                    } else {
                        window.location.href = """ + redirect_url_js + """;
                    }
                </script>
                <p>Google Calendar bağlantısı başarılı. Bu pencere kapanacak...</p>
            </body>
            </html>
            """
        )
    except GoogleCalendarError as exc:
        error_message_js = json.dumps(str(exc))
        redirect_error_js = json.dumps(f"{frontend_redirect_error_base}&reason={quote_plus(str(exc))}")
        return HTMLResponse(
            content=f"""
            <html>
            <body>
                <script>
                    if (window.opener) {{
                        window.opener.postMessage({{type: 'GOOGLE_CALENDAR_CONNECTED', success: false, error: {error_message_js}}}, '*');
                        window.close();
                    }} else {{
                        window.location.href = {redirect_error_js};
                    }}
                </script>
                <p>Google Calendar bağlantı hatası: {str(exc)}</p>
            </body>
            </html>
            """,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


@router.get("/calendar/google/status", response_model=GoogleCalendarStatusResponse)
async def get_google_calendar_status(
    agent_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> GoogleCalendarStatusResponse:
    resolved_agent_id = agent_id or current_user.id
    integration = db.query(RealEstateGoogleCalendarIntegration).filter(
        RealEstateGoogleCalendarIntegration.tenant_id == current_tenant.id,
        RealEstateGoogleCalendarIntegration.agent_id == resolved_agent_id,
    ).first()
    if not integration:
        return GoogleCalendarStatusResponse(connected=False, status="inactive", calendar_id=None)
    return GoogleCalendarStatusResponse(
        connected=integration.status == "active",
        status=integration.status,
        calendar_id=integration.calendar_id,
    )


@router.get("/calendar/google/diagnostics", response_model=GoogleCalendarDiagnosticsResponse)
async def get_google_calendar_diagnostics(
    live: bool = Query(False, description="Canlı OAuth endpoint probe çalıştır"),
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
) -> GoogleCalendarDiagnosticsResponse:
    service = GoogleCalendarService(db)
    diagnostics = service.get_diagnostics()
    if live:
        diagnostics["live_probe"] = await service.probe_oauth_dialog()
    return GoogleCalendarDiagnosticsResponse(**diagnostics)


@router.delete("/calendar/google/disconnect", response_model=dict)
async def disconnect_google_calendar(
    agent_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["settings:write"]))
) -> dict[str, bool]:
    resolved_agent_id = agent_id or current_user.id
    disconnected = GoogleCalendarService(db).disconnect_agent_integration(current_tenant.id, resolved_agent_id)
    return {"disconnected": disconnected}


@router.post("/pdf/generate", response_model=ListingSummaryPdfResponse)
async def generate_listing_summary_pdf(
    payload: ListingSummaryPdfRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> ListingSummaryPdfResponse:
    service = RealEstateService(db)
    try:
        summary, pdf_bytes, filename = service.generate_listing_summary_pdf(
            current_tenant.id,
            payload.listing_ids,
            lead_id=payload.lead_id,
        )
    except ValueError as exc:
        if str(exc) == "pdf_limit_reached":
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Aylık PDF limitine ulaşıldı.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    media_id = None
    whatsapp_sent = False
    if payload.send_whatsapp:
        if not payload.lead_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WhatsApp gönderimi için lead_id zorunludur.")
        send_result = await service.send_listing_summary_pdf_to_lead(
            tenant_id=current_tenant.id,
            lead_id=payload.lead_id,
            pdf_bytes=pdf_bytes,
            filename=filename,
        )
        media_id = send_result.get("media_id")
        whatsapp_sent = True

    return ListingSummaryPdfResponse(
        filename=filename,
        item_count=len(summary.get("items", [])),
        whatsapp_sent=whatsapp_sent,
        media_id=media_id,
        summary=summary,
    )


@router.post("/pdf/download")
async def download_listing_summary_pdf(
    payload: ListingSummaryPdfRequest,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> Response:
    try:
        summary, pdf_bytes, filename = RealEstateService(db).generate_listing_summary_pdf(
            current_tenant.id,
            payload.listing_ids,
            lead_id=payload.lead_id,
        )
    except ValueError as exc:
        if str(exc) == "pdf_limit_reached":
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Aylık PDF limitine ulaşıldı.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    _ = summary
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/leads/{lead_id}/seller-service-report", response_model=dict)
async def send_seller_service_report(
    lead_id: UUID,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
) -> dict[str, Any]:
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.tenant_id == current_tenant.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead bulunamadı")

    try:
        result = await RealEstateService(db).send_seller_service_report(current_tenant.id, lead_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return result


@router.post("/reports/weekly/send", response_model=dict)
async def send_weekly_report_now(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["dashboard:edit"]))
) -> dict[str, Any]:
    return RealEstateService(db).dispatch_weekly_report_if_due(current_tenant.id, force=True)


@router.get("/reports/weekly/download")
async def download_weekly_report_pdf(
    week_start: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    _: None = Depends(require_permissions(["tools:read"]))
) -> Response:
    service = RealEstateService(db)
    try:
        relative_path, file_bytes = service.get_weekly_report_file(current_tenant.id, week_start)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Haftalık rapor PDF bulunamadı")

    filename = relative_path.rsplit("/", 1)[-1]
    return Response(
        content=file_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
