from __future__ import annotations

import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
import app.models  # noqa: F401
from app.api.routers.whatsapp_webhook import process_template_status_event
from app.models.real_estate import RealEstateTemplateRegistry
from app.models.tenant import Tenant
from app.models.user import User
from app.models.whatsapp_account import WhatsAppAccount


def _build_session():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def test_template_status_event_updates_registry():
    db = _build_session()

    owner = User(
        email="owner-template@test.com",
        password_hash="hash",
        full_name="Owner Template",
        is_admin=False,
        is_active=True,
    )
    db.add(owner)
    db.flush()

    tenant = Tenant(name="Template Tenant", owner_id=owner.id, settings={})
    db.add(tenant)
    db.flush()

    account = WhatsAppAccount(
        tenant_id=tenant.id,
        waba_id="waba_123",
        is_active=True,
    )
    db.add(account)
    db.flush()

    template = RealEstateTemplateRegistry(
        tenant_id=tenant.id,
        name="re_followup_recovery_1",
        category="followup",
        language="tr",
        meta_template_id="re_followup_recovery_1",
        variables_schema={},
        status="draft",
        is_approved=False,
    )
    db.add(template)
    db.commit()

    asyncio.run(
        process_template_status_event(
            "waba_123",
            {
                "event": "APPROVED",
                "message_template_id": "re_followup_recovery_1",
                "message_template_name": "re_followup_recovery_1",
            },
            db,
        )
    )

    db.refresh(template)
    assert template.status == "approved"
    assert template.is_approved is True

    db.close()
