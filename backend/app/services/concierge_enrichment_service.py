"""Concierge business enrichment workflow.

The user should not have to fill a long setup form. This service opens an
internal enrichment task and keeps tenant-level state so the product can keep
running while the company team completes the business knowledge profile.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.models.tenant import Tenant
from app.models.ticket import Ticket, TicketMessage
from app.models.user import User
from app.services.system_event_service import SystemEventService


class ConciergeEnrichmentService:
    def __init__(self, db: Session):
        self.db = db

    def ensure_started(self, tenant: Tenant, user: User | None = None) -> dict:
        settings = dict(tenant.settings or {})
        enrichment = dict(settings.get("concierge_enrichment") or {})
        if enrichment.get("status") in {"pending", "in_progress", "completed"}:
            return enrichment

        ticket = Ticket(
            tenant_id=str(tenant.id),
            requester_id=str(user.id) if user else None,
            subject=f"Concierge bilgi formasyonu: {tenant.name}",
            status="open",
            priority="high",
            last_activity_at=utc_now_naive(),
        )
        self.db.add(ticket)
        self.db.flush()

        self.db.add(
            TicketMessage(
                ticket_id=ticket.id,
                sender_id=str(user.id) if user else None,
                sender_type="system",
                body=(
                    "Yeni müşteri için bilgi formasyonu hazırlanmalı.\n"
                    f"- İşletme: {tenant.name}\n"
                    f"- Kullanıcı: {user.full_name if user else 'Bilinmiyor'}\n"
                    f"- E-posta: {user.email if user else 'Bilinmiyor'}\n"
                    "- Hedef: Kullanıcıyı form doldurmaya zorlamadan sektör, hizmetler, sık sorulan sorular, "
                    "ton ve operasyon kurallarını tenant settings.business_profile alanına işlemek."
                ),
            )
        )

        enrichment = {
            "status": "pending",
            "ticket_id": ticket.id,
            "started_at": utc_now_naive().isoformat(),
            "source": "auto_concierge",
        }
        settings["concierge_enrichment"] = enrichment
        settings.setdefault(
            "business_profile",
            {
                "status": "needs_enrichment",
                "source": "auto_concierge",
                "business_name": tenant.name,
                "industry": "unknown",
                "tone": "professional",
                "summary": "",
                "services": [],
                "faq": [],
            },
        )
        tenant.settings = settings
        self.db.commit()

        SystemEventService(self.db).log(
            tenant_id=str(tenant.id),
            source="concierge",
            level="info",
            code="CONCIERGE_ENRICHMENT_OPENED",
            message="Concierge business enrichment task opened",
            meta_json={"ticket_id": ticket.id},
        )
        return enrichment
