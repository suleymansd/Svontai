"""
Analytics service for tracking and aggregating usage metrics.
"""

import uuid
from datetime import datetime, date, timedelta
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.usage_log import UsageLog, UsageType, DailyStats
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.lead import Lead


class AnalyticsService:
    """Service for tracking and querying analytics."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def log_usage(
        self,
        tenant_id: uuid.UUID,
        usage_type: UsageType,
        bot_id: Optional[uuid.UUID] = None,
        count: int = 1,
        metadata: Optional[dict] = None
    ):
        """Log a usage event."""
        log = UsageLog(
            tenant_id=tenant_id,
            bot_id=bot_id,
            usage_type=usage_type.value,
            count=count,
            extra_data=metadata or {}
        )
        self.db.add(log)
        self.db.commit()
    
    def get_or_create_daily_stats(
        self,
        tenant_id: uuid.UUID,
        stat_date: Optional[date] = None
    ) -> DailyStats:
        """Get or create daily stats record."""
        if stat_date is None:
            stat_date = date.today()
        
        stats = self.db.query(DailyStats).filter(
            and_(
                DailyStats.tenant_id == tenant_id,
                DailyStats.date == stat_date
            )
        ).first()
        
        if not stats:
            stats = DailyStats(
                tenant_id=tenant_id,
                date=stat_date
            )
            self.db.add(stats)
            self.db.commit()
            self.db.refresh(stats)
        
        return stats
    
    def increment_stat(
        self,
        tenant_id: uuid.UUID,
        stat_name: str,
        count: int = 1
    ):
        """Increment a daily stat."""
        stats = self.get_or_create_daily_stats(tenant_id)
        
        if hasattr(stats, stat_name):
            current_value = getattr(stats, stat_name)
            setattr(stats, stat_name, current_value + count)
            stats.updated_at = datetime.utcnow()
            self.db.commit()
    
    def get_dashboard_stats(self, tenant_id: uuid.UUID) -> dict:
        """Get dashboard statistics for a tenant."""
        today = date.today()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Get today's stats
        today_stats = self.get_or_create_daily_stats(tenant_id, today)
        
        # Get weekly totals
        weekly_stats = self.db.query(
            func.sum(DailyStats.messages_sent).label('messages_sent'),
            func.sum(DailyStats.messages_received).label('messages_received'),
            func.sum(DailyStats.conversations_started).label('conversations_started'),
            func.sum(DailyStats.leads_captured).label('leads_captured')
        ).filter(
            and_(
                DailyStats.tenant_id == tenant_id,
                DailyStats.date >= week_ago
            )
        ).first()
        
        # Get monthly totals
        monthly_stats = self.db.query(
            func.sum(DailyStats.messages_sent).label('messages_sent'),
            func.sum(DailyStats.messages_received).label('messages_received'),
            func.sum(DailyStats.conversations_started).label('conversations_started'),
            func.sum(DailyStats.leads_captured).label('leads_captured')
        ).filter(
            and_(
                DailyStats.tenant_id == tenant_id,
                DailyStats.date >= month_ago
            )
        ).first()
        
        # Calculate conversation count from database
        total_conversations = self.db.query(func.count(Conversation.id)).join(
            Conversation.bot
        ).filter(
            Conversation.bot.has(tenant_id=tenant_id)
        ).scalar() or 0
        
        # Calculate total leads
        total_leads = self.db.query(func.count(Lead.id)).filter(
            Lead.tenant_id == tenant_id,
            Lead.is_deleted == False
        ).scalar() or 0
        
        return {
            "today": {
                "messages_sent": today_stats.messages_sent,
                "messages_received": today_stats.messages_received,
                "ai_responses": today_stats.ai_responses,
                "conversations_started": today_stats.conversations_started,
                "leads_captured": today_stats.leads_captured
            },
            "weekly": {
                "messages_sent": weekly_stats.messages_sent or 0,
                "messages_received": weekly_stats.messages_received or 0,
                "conversations_started": weekly_stats.conversations_started or 0,
                "leads_captured": weekly_stats.leads_captured or 0
            },
            "monthly": {
                "messages_sent": monthly_stats.messages_sent or 0,
                "messages_received": monthly_stats.messages_received or 0,
                "conversations_started": monthly_stats.conversations_started or 0,
                "leads_captured": monthly_stats.leads_captured or 0
            },
            "totals": {
                "conversations": total_conversations,
                "leads": total_leads
            }
        }
    
    def get_chart_data(
        self,
        tenant_id: uuid.UUID,
        days: int = 30
    ) -> List[dict]:
        """Get daily stats for charts."""
        start_date = date.today() - timedelta(days=days)
        
        stats = self.db.query(DailyStats).filter(
            and_(
                DailyStats.tenant_id == tenant_id,
                DailyStats.date >= start_date
            )
        ).order_by(DailyStats.date).all()
        
        # Create a map of existing stats
        stats_map = {s.date: s for s in stats}
        
        # Fill in missing days with zeros
        result = []
        current_date = start_date
        while current_date <= date.today():
            if current_date in stats_map:
                s = stats_map[current_date]
                result.append({
                    "date": current_date.isoformat(),
                    "messages_sent": s.messages_sent,
                    "messages_received": s.messages_received,
                    "ai_responses": s.ai_responses,
                    "conversations": s.conversations_started,
                    "leads": s.leads_captured
                })
            else:
                result.append({
                    "date": current_date.isoformat(),
                    "messages_sent": 0,
                    "messages_received": 0,
                    "ai_responses": 0,
                    "conversations": 0,
                    "leads": 0
                })
            current_date += timedelta(days=1)
        
        return result
    
    def get_bot_stats(
        self,
        tenant_id: uuid.UUID,
        bot_id: uuid.UUID
    ) -> dict:
        """Get statistics for a specific bot."""
        # Count conversations
        total_conversations = self.db.query(func.count(Conversation.id)).filter(
            Conversation.bot_id == bot_id
        ).scalar() or 0
        
        # Count messages
        message_counts = self.db.query(
            func.count(Message.id).label('total'),
            func.sum(
                func.case([(Message.sender == 'bot', 1)], else_=0)
            ).label('bot_messages'),
            func.sum(
                func.case([(Message.sender == 'user', 1)], else_=0)
            ).label('user_messages')
        ).join(Conversation).filter(
            Conversation.bot_id == bot_id
        ).first()
        
        # Count leads
        total_leads = self.db.query(func.count(Lead.id)).filter(
            Lead.bot_id == bot_id,
            Lead.is_deleted == False
        ).scalar() or 0
        
        return {
            "total_conversations": total_conversations,
            "total_messages": message_counts.total or 0,
            "bot_messages": message_counts.bot_messages or 0,
            "user_messages": message_counts.user_messages or 0,
            "total_leads": total_leads,
            "response_rate": round(
                (message_counts.bot_messages / message_counts.user_messages * 100)
                if message_counts.user_messages else 0, 1
            )
        }
    
    def get_source_breakdown(self, tenant_id: uuid.UUID) -> dict:
        """Get message breakdown by source."""
        today = date.today()
        stats = self.get_or_create_daily_stats(tenant_id, today)
        
        total = stats.whatsapp_messages + stats.widget_messages
        
        return {
            "whatsapp": stats.whatsapp_messages,
            "widget": stats.widget_messages,
            "total": total,
            "whatsapp_percent": round(stats.whatsapp_messages / total * 100, 1) if total > 0 else 0,
            "widget_percent": round(stats.widget_messages / total * 100, 1) if total > 0 else 0
        }


def get_analytics_service(db: Session) -> AnalyticsService:
    """Get analytics service instance."""
    return AnalyticsService(db)

