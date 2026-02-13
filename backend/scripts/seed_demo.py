"""
Seed demo data for SvontAI.

Run:
  python backend/scripts/seed_demo.py
"""

import uuid
from datetime import datetime, timedelta

from app.db.session import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User
from app.models.tenant import Tenant, generate_slug
from app.models.tenant_membership import TenantMembership
from app.models.tool import Tool
from app.models.system_event import SystemEvent
from app.models.ticket import Ticket, TicketMessage
from app.services.rbac_service import RbacService
from app.services.subscription_service import SubscriptionService


def get_or_create_user(db, email: str, full_name: str, password: str, is_admin: bool) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(
        email=email,
        full_name=full_name,
        password_hash=get_password_hash(password),
        is_admin=is_admin
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_or_create_tenant(db, owner: User, name: str) -> Tenant:
    existing = db.query(Tenant).filter(Tenant.owner_id == owner.id).first()
    if existing:
        return existing
    tenant = Tenant(
        name=name,
        owner_id=owner.id,
        slug=generate_slug(name)
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def ensure_membership(db, tenant: Tenant, user: User, role_name: str) -> None:
    existing = db.query(TenantMembership).filter(
        TenantMembership.tenant_id == tenant.id,
        TenantMembership.user_id == user.id
    ).first()
    if existing:
        return

    rbac = RbacService(db)
    rbac.ensure_defaults()
    role = rbac.get_role_by_name(role_name)
    if not role:
        return

    membership = TenantMembership(
        tenant_id=tenant.id,
        user_id=user.id,
        role_id=role.id,
        status="active"
    )
    db.add(membership)
    db.commit()


def seed_tools(db) -> None:
    tools = [
        {
            "key": "whatsapp",
            "name": "WhatsApp Messaging",
            "description": "Inbound and outbound messaging via Meta API.",
            "category": "Messaging",
            "icon": "message-circle",
            "tags": ["WhatsApp", "Messaging"],
            "required_plan": "starter",
            "status": "active",
            "is_public": True,
            "coming_soon": False
        },
        {
            "key": "crm",
            "name": "CRM Enrichment",
            "description": "Sync contacts and enrich lead data.",
            "category": "CRM",
            "icon": "contact",
            "tags": ["CRM", "Leads"],
            "required_plan": "growth",
            "status": "active",
            "is_public": True,
            "coming_soon": False
        },
        {
            "key": "scheduler",
            "name": "Smart Scheduler",
            "description": "Automated booking and confirmations.",
            "category": "Scheduling",
            "icon": "calendar",
            "tags": ["Scheduling", "Automation"],
            "required_plan": "starter",
            "status": "active",
            "is_public": True,
            "coming_soon": False
        }
    ]

    for tool_data in tools:
        existing = db.query(Tool).filter(Tool.key == tool_data["key"]).first()
        if existing:
            continue
        db.add(Tool(**tool_data))
    db.commit()


def seed_events(db, tenant: Tenant) -> None:
    existing = db.query(SystemEvent).filter(SystemEvent.tenant_id == str(tenant.id)).first()
    if existing:
        return

    now = datetime.utcnow()
    events = [
        SystemEvent(
            tenant_id=str(tenant.id),
            source="whatsapp_webhook",
            level="info",
            code="WH_INBOUND",
            message="Inbound message received",
            meta_json={"count": 1},
            created_at=now - timedelta(minutes=15)
        ),
        SystemEvent(
            tenant_id=str(tenant.id),
            source="n8n",
            level="warn",
            code="N8N_TIMEOUT",
            message="Workflow timeout",
            meta_json={"workflow_id": "demo-workflow"},
            created_at=now - timedelta(minutes=10)
        ),
        SystemEvent(
            tenant_id=str(tenant.id),
            source="subscription",
            level="warn",
            code="MESSAGE_LIMIT_EXCEEDED",
            message="Monthly message limit exceeded",
            meta_json={"limit": 1000, "used": 1000},
            created_at=now - timedelta(minutes=5)
        )
    ]
    db.add_all(events)
    db.commit()


def seed_ticket(db, tenant: Tenant, requester: User) -> None:
    existing = db.query(Ticket).filter(Ticket.tenant_id == str(tenant.id)).first()
    if existing:
        return

    ticket = Ticket(
        tenant_id=str(tenant.id),
        requester_id=str(requester.id),
        subject="Demo ticket: WhatsApp delivery issue",
        status="open",
        priority="high",
        last_activity_at=datetime.utcnow()
    )
    db.add(ticket)
    db.flush()

    message = TicketMessage(
        ticket_id=ticket.id,
        sender_id=str(requester.id),
        sender_type="user",
        body="Outbound messages are not being delivered."
    )
    db.add(message)
    db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        demo_admin = get_or_create_user(
            db,
            email="admin@svontai.com",
            full_name="SvontAI Admin",
            password="Admin12345",
            is_admin=True
        )
        demo_user = get_or_create_user(
            db,
            email="demo@svontai.com",
            full_name="Demo Customer",
            password="Demo12345",
            is_admin=False
        )
        tenant = get_or_create_tenant(db, demo_user, "SvontAI Demo Co")
        ensure_membership(db, tenant, demo_user, "owner")
        ensure_membership(db, tenant, demo_admin, "system_admin")

        SubscriptionService(db).create_subscription(tenant.id, "starter")
        seed_tools(db)
        seed_events(db, tenant)
        seed_ticket(db, tenant, demo_user)

        print("Seed complete.")
        print("Admin login: admin@svontai.com / Admin12345")
        print("Customer login: demo@svontai.com / Demo12345")
    finally:
        db.close()


if __name__ == "__main__":
    main()
