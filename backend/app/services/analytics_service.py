"""
Analytics service for tracking and aggregating usage metrics.
"""

import uuid
from datetime import UTC, datetime, date, timedelta
from app.core.time import utc_now_naive
from typing import Optional, List
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.appointment import Appointment
from app.models.automation import AutomationRun, AutomationRunStatus
from app.models.bot import Bot
from app.models.usage_log import UsageLog, UsageType, DailyStats
from app.models.conversation import Conversation
from app.models.message import Message, MessageSender
from app.models.lead import Lead
from app.models.tenant import Tenant


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
            stats.updated_at = utc_now_naive()
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

    def get_operational_report(self, tenant: Tenant, period: str = "today") -> dict:
        """Build a real-data operational summary suitable for mobile Notes apps."""
        timezone_name = str((tenant.settings or {}).get("timezone") or "Europe/Istanbul")
        try:
            timezone = ZoneInfo(timezone_name)
        except Exception:
            timezone_name = "Europe/Istanbul"
            timezone = ZoneInfo(timezone_name)

        now_local = datetime.now(timezone)
        if period == "week":
            start_local = (now_local - timedelta(days=6)).replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            period_label = "Son 7 Gün"
        else:
            start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
            period_label = "Bugün"
        start_utc = start_local.astimezone(UTC).replace(tzinfo=None)

        tenant_message_query = self.db.query(Message).join(
            Conversation, Message.conversation_id == Conversation.id
        ).join(Bot, Conversation.bot_id == Bot.id).filter(
            Bot.tenant_id == tenant.id,
            Message.created_at >= start_utc,
        )
        incoming_messages = tenant_message_query.filter(
            Message.sender == MessageSender.USER.value
        ).count()
        ai_replies = tenant_message_query.filter(
            Message.sender == MessageSender.BOT.value
        ).count()
        conversations = self.db.query(func.count(Conversation.id)).join(
            Bot, Conversation.bot_id == Bot.id
        ).filter(
            Bot.tenant_id == tenant.id,
            Conversation.created_at >= start_utc,
        ).scalar() or 0
        leads = self.db.query(func.count(Lead.id)).filter(
            Lead.tenant_id == tenant.id,
            Lead.is_deleted.is_(False),
            Lead.created_at >= start_utc,
        ).scalar() or 0
        appointments = self.db.query(func.count(Appointment.id)).filter(
            Appointment.tenant_id == tenant.id,
            Appointment.created_at >= start_utc,
        ).scalar() or 0
        successful_runs = self.db.query(func.count(AutomationRun.id)).filter(
            AutomationRun.tenant_id == str(tenant.id),
            AutomationRun.created_at >= start_utc,
            AutomationRun.status == AutomationRunStatus.SUCCESS.value,
        ).scalar() or 0
        failed_runs = self.db.query(func.count(AutomationRun.id)).filter(
            AutomationRun.tenant_id == str(tenant.id),
            AutomationRun.created_at >= start_utc,
            AutomationRun.status.in_([
                AutomationRunStatus.FAILED.value,
                AutomationRunStatus.TIMEOUT.value,
            ]),
        ).scalar() or 0

        response_rate = round((ai_replies / incoming_messages) * 100, 1) if incoming_messages else 0.0
        status_text = (
            "SvontAI aktif ve müşteri mesajlarını yanıtlıyor."
            if incoming_messages == 0 or ai_replies > 0
            else "Müşteri mesajı alındı fakat otomatik yanıt görünmüyor; sistem durumunu kontrol edin."
        )
        generated_at = now_local.strftime("%d.%m.%Y %H:%M")
        title = f"{tenant.name} - SvontAI {period_label} Raporu"
        summary = (
            f"{incoming_messages} müşteri mesajı alındı, {ai_replies} otomatik yanıt gönderildi, "
            f"{leads} yeni müşteri ve {appointments} randevu kaydı oluştu."
        )
        report_text = "\n".join([
            title,
            f"Oluşturulma: {generated_at} ({timezone_name})",
            "",
            "SİSTEM DURUMU",
            status_text,
            "",
            "PERFORMANS ÖZETİ",
            f"- Gelen mesaj: {incoming_messages}",
            f"- Otomatik AI yanıtı: {ai_replies}",
            f"- Yanıt oranı: %{response_rate}",
            f"- Yeni konuşma: {conversations}",
            f"- Yeni müşteri/lead: {leads}",
            f"- Randevu: {appointments}",
            f"- Başarılı otomasyon: {successful_runs}",
            f"- Hatalı otomasyon: {failed_runs}",
            "",
            "KISA ÖZET",
            summary,
        ])
        return {
            "period": period,
            "title": title,
            "summary": summary,
            "text": report_text,
            "generated_at": now_local.isoformat(),
            "timezone": timezone_name,
            "metrics": {
                "incoming_messages": incoming_messages,
                "ai_replies": ai_replies,
                "response_rate": response_rate,
                "conversations": conversations,
                "leads": leads,
                "appointments": appointments,
                "successful_automations": successful_runs,
                "failed_automations": failed_runs,
            },
        }


def get_analytics_service(db: Session) -> AnalyticsService:
    """Get analytics service instance."""
    return AnalyticsService(db)
