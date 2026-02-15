"""
Background appointment reminder dispatch.

In production this should eventually move to a dedicated worker/queue, but a
single-instance periodic loop is good enough for MVP and keeps infra simple.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReminderDispatchResult:
    sent_before: int = 0
    sent_after: int = 0


class AppointmentReminderService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _format_datetime_label(value: datetime) -> str:
        return value.strftime("%d.%m.%Y %H:%M")

    def dispatch_due_reminders(self, now: datetime | None = None) -> ReminderDispatchResult:
        now = now or datetime.utcnow()

        appointments = self.db.query(Appointment).filter(
            Appointment.status != "cancelled",
            Appointment.customer_email.isnot(None),
        ).all()

        to_send_before: list[Appointment] = []
        to_send_after: list[Appointment] = []

        for appointment in appointments:
            if not appointment.customer_email:
                continue

            before_trigger = appointment.starts_at - timedelta(minutes=appointment.reminder_before_minutes)
            if (
                appointment.reminder_before_sent_at is None
                and now >= before_trigger
                and now <= appointment.starts_at + timedelta(minutes=5)
            ):
                appointment.reminder_before_sent_at = now
                to_send_before.append(appointment)

            after_trigger = appointment.starts_at + timedelta(minutes=30)
            if appointment.reminder_after_sent_at is None and now >= after_trigger:
                appointment.reminder_after_sent_at = now
                to_send_after.append(appointment)

        if not to_send_before and not to_send_after:
            return ReminderDispatchResult()

        # Persist "sent" flags first to avoid duplicate sends.
        self.db.commit()

        sent_before = 0
        for appointment in to_send_before:
            ok = EmailService.send_appointment_before_reminder_email(
                appointment.customer_email,
                appointment.customer_name,
                appointment.subject,
                self._format_datetime_label(appointment.starts_at)
            )
            if ok:
                sent_before += 1

        sent_after = 0
        for appointment in to_send_after:
            ok = EmailService.send_appointment_after_followup_email(
                appointment.customer_email,
                appointment.customer_name,
                appointment.subject
            )
            if ok:
                sent_after += 1

        if sent_before or sent_after:
            logger.info(
                "Appointment reminders dispatched",
                extra={"sent_before": sent_before, "sent_after": sent_after}
            )

        return ReminderDispatchResult(sent_before=sent_before, sent_after=sent_after)

