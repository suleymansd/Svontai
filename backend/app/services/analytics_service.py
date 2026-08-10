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
from app.models.voice_automation import OutboundCallJob, OutboundCallJobStatus


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
        automation_runs = self.db.query(
            AutomationRun.status,
            AutomationRun.n8n_workflow_id,
            AutomationRun.channel,
            AutomationRun.created_at,
        ).filter(
            AutomationRun.tenant_id == str(tenant.id),
            AutomationRun.created_at >= start_utc,
            AutomationRun.status.in_([
                AutomationRunStatus.SUCCESS.value,
                AutomationRunStatus.FAILED.value,
                AutomationRunStatus.TIMEOUT.value,
            ]),
        ).all()
        successful_runs = sum(
            1 for run in automation_runs
            if run.status == AutomationRunStatus.SUCCESS.value
        )
        failed_automation_runs = [
            run for run in automation_runs
            if run.status in {
                AutomationRunStatus.FAILED.value,
                AutomationRunStatus.TIMEOUT.value,
            }
        ]
        failed_runs = len(failed_automation_runs)
        latest_success_by_workflow: dict[tuple[str, str], datetime] = {}
        for run in automation_runs:
            if run.status != AutomationRunStatus.SUCCESS.value:
                continue
            workflow_key = (run.n8n_workflow_id or "default", run.channel)
            latest_success = latest_success_by_workflow.get(workflow_key)
            if latest_success is None or run.created_at > latest_success:
                latest_success_by_workflow[workflow_key] = run.created_at

        unresolved_failed_runs = sum(
            1
            for run in failed_automation_runs
            if (
                latest_success_by_workflow.get(
                    (run.n8n_workflow_id or "default", run.channel)
                ) is None
                or run.created_at
                > latest_success_by_workflow[
                    (run.n8n_workflow_id or "default", run.channel)
                ]
            )
        )
        recovered_failed_runs = failed_runs - unresolved_failed_runs

        response_rate = round((ai_replies / incoming_messages) * 100, 1) if incoming_messages else 0.0
        attention_reasons: list[str] = []
        if incoming_messages > 0 and ai_replies == 0:
            attention_reasons.append(
                "Müşteri mesajı alındı fakat otomatik yanıt görünmüyor."
            )
        if unresolved_failed_runs > 0:
            attention_reasons.append(
                f"Son başarılı çalışmadan sonra {unresolved_failed_runs} otomasyon hatası var."
            )
        if attention_reasons:
            status_text = " ".join(attention_reasons)
        elif recovered_failed_runs > 0:
            status_text = (
                "SvontAI aktif çalışıyor. "
                f"{recovered_failed_runs} geçmiş otomasyon hatası daha sonraki başarılı "
                "çalışmayla düzeldi."
            )
        else:
            status_text = "SvontAI aktif ve müşteri mesajlarını yanıtlıyor."
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
            f"- Başarısız otomasyon denemesi: {failed_runs}",
            f"- Açık otomasyon hatası: {unresolved_failed_runs}",
            f"- Sonraki başarıyla düzelen hata: {recovered_failed_runs}",
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
            "health": {
                "healthy": not attention_reasons,
                "attention_reasons": attention_reasons,
            },
            "metrics": {
                "incoming_messages": incoming_messages,
                "ai_replies": ai_replies,
                "response_rate": response_rate,
                "conversations": conversations,
                "leads": leads,
                "appointments": appointments,
                "successful_automations": successful_runs,
                "failed_automations": failed_runs,
                "unresolved_automation_failures": unresolved_failed_runs,
                "recovered_automation_failures": recovered_failed_runs,
            },
        }

    def get_customer_success_summary(self, tenant_id: uuid.UUID, days: int = 30) -> dict:
        """Return real usage outcomes and a transparent time-saved estimate."""
        start_at = utc_now_naive() - timedelta(days=days)
        tenant_messages = self.db.query(Message).join(
            Conversation, Message.conversation_id == Conversation.id
        ).join(Bot, Conversation.bot_id == Bot.id).filter(
            Bot.tenant_id == tenant_id,
            Message.created_at >= start_at,
        )
        incoming = tenant_messages.filter(Message.sender == MessageSender.USER.value).count()
        ai_replies = tenant_messages.filter(Message.sender == MessageSender.BOT.value).count()
        conversations = self.db.query(func.count(Conversation.id)).join(Bot).filter(
            Bot.tenant_id == tenant_id,
            Conversation.created_at >= start_at,
        ).scalar() or 0
        handoffs = self.db.query(func.count(Conversation.id)).join(Bot).filter(
            Bot.tenant_id == tenant_id,
            Conversation.updated_at >= start_at,
            Conversation.status.in_(["waiting", "human_takeover"]),
        ).scalar() or 0
        leads = self.db.query(func.count(Lead.id)).filter(
            Lead.tenant_id == tenant_id,
            Lead.is_deleted.is_(False),
            Lead.created_at >= start_at,
        ).scalar() or 0
        appointments = self.db.query(func.count(Appointment.id)).filter(
            Appointment.tenant_id == tenant_id,
            Appointment.created_at >= start_at,
        ).scalar() or 0
        successful_automations = self.db.query(func.count(AutomationRun.id)).filter(
            AutomationRun.tenant_id == str(tenant_id),
            AutomationRun.created_at >= start_at,
            AutomationRun.status == AutomationRunStatus.SUCCESS.value,
        ).scalar() or 0

        estimated_minutes = int(ai_replies * 2 + appointments * 6 + successful_automations * 3)
        return {
            "period_days": days,
            "messages_received": int(incoming),
            "ai_replies": int(ai_replies),
            "response_coverage": round((ai_replies / incoming) * 100, 1) if incoming else 0.0,
            "conversations": int(conversations),
            "new_customers": int(leads),
            "appointments": int(appointments),
            "successful_automations": int(successful_automations),
            "human_handoffs": int(handoffs),
            "estimated_time_saved_minutes": estimated_minutes,
            "estimate_method": "AI yanıtı başına 2 dk, randevu başına 6 dk, başarılı otomasyon başına 3 dk.",
        }

    def get_action_center(self, tenant_id: uuid.UUID, window_hours: int = 24) -> dict:
        """Return tenant-scoped work that needs attention plus the next appointments."""
        now = utc_now_naive()
        recent_at = now - timedelta(hours=window_hours)
        upcoming_until = now + timedelta(hours=24)
        items: list[dict] = []

        handoff_query = self.db.query(Conversation).join(Bot).filter(
            Bot.tenant_id == tenant_id,
            Conversation.status.in_(["waiting", "human_takeover"]),
        )
        handoff_count = handoff_query.count()
        handoffs = handoff_query.order_by(Conversation.updated_at.desc()).limit(5).all()
        for conversation in handoffs:
            customer = conversation.customer_name or conversation.customer_phone or "Müşteri"
            reasons = list((conversation.extra_data or {}).get("handoff_reason") or [])
            description = (
                f"{customer} insan desteği bekliyor."
                if not reasons
                else f"{customer} için AI güvenli şekilde konuşmayı ekibinize devretti."
            )
            items.append({
                "id": f"handoff:{conversation.id}",
                "kind": "human_handoff",
                "severity": "high",
                "title": "Müşteri yanıt bekliyor",
                "description": description,
                "href": f"/dashboard/operator?conversation={conversation.id}",
                "cta_label": "Konuşmayı Aç",
                "occurred_at": conversation.updated_at,
            })

        automation_runs = self.db.query(AutomationRun).filter(
            AutomationRun.tenant_id == str(tenant_id),
            AutomationRun.created_at >= recent_at,
            AutomationRun.status.in_([
                AutomationRunStatus.SUCCESS.value,
                AutomationRunStatus.FAILED.value,
                AutomationRunStatus.TIMEOUT.value,
            ]),
        ).order_by(AutomationRun.created_at.asc()).all()
        latest_success_by_workflow: dict[tuple[str, str], datetime] = {}
        for run in automation_runs:
            if run.status == AutomationRunStatus.SUCCESS.value:
                latest_success_by_workflow[(run.n8n_workflow_id or "default", run.channel)] = run.created_at
        unresolved_automation_runs = [
            run
            for run in automation_runs
            if run.status in {AutomationRunStatus.FAILED.value, AutomationRunStatus.TIMEOUT.value}
            and run.created_at > latest_success_by_workflow.get(
                (run.n8n_workflow_id or "default", run.channel),
                datetime.min,
            )
        ]
        if unresolved_automation_runs:
            latest_run = max(unresolved_automation_runs, key=lambda run: run.created_at)
            items.append({
                "id": "automation:unresolved",
                "kind": "automation_failure",
                "severity": "high",
                "title": "Otomasyon kontrolü gerekiyor",
                "description": f"Son {window_hours} saatte düzelmemiş {len(unresolved_automation_runs)} otomasyon işlemi var.",
                "href": "/dashboard/errors",
                "cta_label": "Durumu İncele",
                "occurred_at": latest_run.created_at,
            })

        failed_call_query = self.db.query(OutboundCallJob).filter(
            OutboundCallJob.tenant_id == tenant_id,
            OutboundCallJob.status == OutboundCallJobStatus.FAILED.value,
            OutboundCallJob.updated_at >= recent_at,
        )
        failed_call_count = failed_call_query.count()
        latest_failed_call = failed_call_query.order_by(OutboundCallJob.updated_at.desc()).first()
        if latest_failed_call:
            items.append({
                "id": "voice:failed",
                "kind": "voice_failure",
                "severity": "medium",
                "title": "Tamamlanamayan arama var",
                "description": f"Son {window_hours} saatte {failed_call_count} arama tamamlanamadı.",
                "href": "/dashboard/calls",
                "cta_label": "Aramaları Aç",
                "occurred_at": latest_failed_call.updated_at,
            })

        calendar_failure_query = self.db.query(Appointment).filter(
            Appointment.tenant_id == tenant_id,
            Appointment.status == "scheduled",
            Appointment.calendar_sync_status == "failed",
        )
        calendar_failure_count = calendar_failure_query.count()
        latest_calendar_failure = calendar_failure_query.order_by(Appointment.updated_at.desc()).first()
        if latest_calendar_failure:
            items.append({
                "id": "calendar:sync-failed",
                "kind": "calendar_sync_failure",
                "severity": "medium",
                "title": "Takvime aktarılamayan randevu var",
                "description": f"{calendar_failure_count} randevu SvontAI'da kayıtlı ancak Google Takvim'e aktarılamadı.",
                "href": "/dashboard/appointments",
                "cta_label": "Randevuları Aç",
                "occurred_at": latest_calendar_failure.updated_at,
            })

        appointments = self.db.query(Appointment).filter(
            Appointment.tenant_id == tenant_id,
            Appointment.status == "scheduled",
            Appointment.starts_at >= now,
            Appointment.starts_at <= upcoming_until,
        ).order_by(Appointment.starts_at.asc()).limit(5).all()

        severity_order = {"high": 0, "medium": 1, "low": 2}
        items.sort(key=lambda item: (severity_order.get(item["severity"], 9), -(item["occurred_at"].timestamp())))
        return {
            "generated_at": now,
            "window_hours": window_hours,
            "required_count": handoff_count + len(unresolved_automation_runs) + failed_call_count + calendar_failure_count,
            "items": items,
            "upcoming_appointments": [
                {
                    "id": str(appointment.id),
                    "customer_name": appointment.customer_name,
                    "subject": appointment.subject,
                    "starts_at": appointment.starts_at,
                    "duration_minutes": appointment.duration_minutes,
                    "href": "/dashboard/appointments",
                }
                for appointment in appointments
            ],
        }


def get_analytics_service(db: Session) -> AnalyticsService:
    """Get analytics service instance."""
    return AnalyticsService(db)
