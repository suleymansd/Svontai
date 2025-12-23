"""
Analytics API router for dashboard statistics and insights.
"""

from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_current_tenant
from app.models.user import User
from app.models.tenant import Tenant
from app.services.analytics_service import AnalyticsService
from app.services.subscription_service import SubscriptionService


router = APIRouter(prefix="/analytics", tags=["analytics"])


# Schemas
class DailyStatsResponse(BaseModel):
    messages_sent: int
    messages_received: int
    ai_responses: int
    conversations_started: int
    leads_captured: int


class DashboardStatsResponse(BaseModel):
    today: DailyStatsResponse
    weekly: dict
    monthly: dict
    totals: dict


class ChartDataPoint(BaseModel):
    date: str
    messages_sent: int
    messages_received: int
    ai_responses: int
    conversations: int
    leads: int


class BotStatsResponse(BaseModel):
    total_conversations: int
    total_messages: int
    bot_messages: int
    user_messages: int
    total_leads: int
    response_rate: float


class SourceBreakdownResponse(BaseModel):
    whatsapp: int
    widget: int
    total: int
    whatsapp_percent: float
    widget_percent: float


# Endpoints
@router.get("/dashboard", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get dashboard statistics for the current tenant."""
    # Check if analytics feature is enabled
    subscription_service = SubscriptionService(db)
    # Allow basic analytics for all plans, detailed for paid
    
    analytics_service = AnalyticsService(db)
    stats = analytics_service.get_dashboard_stats(tenant.id)
    
    return DashboardStatsResponse(
        today=DailyStatsResponse(**stats["today"]),
        weekly=stats["weekly"],
        monthly=stats["monthly"],
        totals=stats["totals"]
    )


@router.get("/chart-data", response_model=list[ChartDataPoint])
async def get_chart_data(
    days: int = Query(default=30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get daily statistics for charts."""
    # Check analytics feature
    subscription_service = SubscriptionService(db)
    if not subscription_service.check_feature(tenant.id, "analytics"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analitik özellikleri için planınızı yükseltin"
        )
    
    analytics_service = AnalyticsService(db)
    data = analytics_service.get_chart_data(tenant.id, days)
    
    return [ChartDataPoint(**point) for point in data]


@router.get("/bot/{bot_id}", response_model=BotStatsResponse)
async def get_bot_stats(
    bot_id: UUID,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get statistics for a specific bot."""
    analytics_service = AnalyticsService(db)
    stats = analytics_service.get_bot_stats(tenant.id, bot_id)
    
    return BotStatsResponse(**stats)


@router.get("/sources", response_model=SourceBreakdownResponse)
async def get_source_breakdown(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get message breakdown by source (WhatsApp vs Widget)."""
    analytics_service = AnalyticsService(db)
    breakdown = analytics_service.get_source_breakdown(tenant.id)
    
    return SourceBreakdownResponse(**breakdown)


@router.get("/usage-summary")
async def get_usage_summary(
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get combined usage and subscription summary."""
    subscription_service = SubscriptionService(db)
    analytics_service = AnalyticsService(db)
    
    usage_stats = subscription_service.get_usage_stats(tenant.id)
    dashboard_stats = analytics_service.get_dashboard_stats(tenant.id)
    
    return {
        "subscription": usage_stats,
        "stats": dashboard_stats
    }

