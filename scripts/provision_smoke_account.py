#!/usr/bin/env python3
"""Provision an idempotent, least-privilege production smoke tenant.

The password is read only from SMARTWA_SMOKE_PASSWORD and is never printed.
Run through `railway run --service Svontai` so the production database URL is
provided by Railway without copying it into GitHub Actions.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import func

import app.models  # noqa: F401 - register all SQLAlchemy relationships
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.tenant import Tenant, generate_slug
from app.models.tenant_membership import TenantMembership
from app.models.tenant_onboarding import TenantOnboarding
from app.models.user import User
from app.services.concierge_enrichment_service import ConciergeEnrichmentService
from app.services.rbac_service import RbacService


def _required_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def run() -> int:
    if settings.ENVIRONMENT != "prod":
        raise RuntimeError("Smoke account provisioning requires ENVIRONMENT=prod")

    email = _required_env("SMARTWA_SMOKE_EMAIL").lower()
    password = _required_env("SMARTWA_SMOKE_PASSWORD")
    if len(password) < 24:
        raise RuntimeError("SMARTWA_SMOKE_PASSWORD must be at least 24 characters")

    db = SessionLocal()
    try:
        user = db.query(User).filter(func.lower(User.email) == email).first()
        created = user is None
        if user is None:
            user = User(
                email=email,
                full_name="SvontAI Uptime Smoke",
                password_hash=get_password_hash(password),
                email_verified=True,
                is_active=True,
                is_admin=False,
            )
            db.add(user)
            db.flush()
        else:
            user.password_hash = get_password_hash(password)
            user.email_verified = True
            user.is_active = True
            user.is_admin = False
            user.failed_login_attempts = 0
            user.locked_until = None

        tenant = db.query(Tenant).filter(Tenant.owner_id == user.id).first()
        if tenant is None:
            tenant = Tenant(
                name="SvontAI Uptime Smoke",
                slug=generate_slug(f"svontai-uptime-smoke-{str(user.id)[:8]}"),
                owner_id=user.id,
                settings={
                    "is_smoke_tenant": True,
                    "setup_mode": "self_serve",
                    "operational_report_email_enabled": False,
                    "daily_operational_report_enabled": False,
                    "weekly_operational_report_enabled": False,
                },
            )
            db.add(tenant)
            db.flush()
        else:
            tenant.settings = {
                **(tenant.settings or {}),
                "is_smoke_tenant": True,
                "operational_report_email_enabled": False,
                "daily_operational_report_enabled": False,
                "weekly_operational_report_enabled": False,
            }

        rbac = RbacService(db)
        rbac.ensure_defaults()
        owner_role = rbac.get_role_by_name("owner")
        if owner_role is None:
            raise RuntimeError("Owner role could not be initialized")
        membership = db.query(TenantMembership).filter(
            TenantMembership.tenant_id == tenant.id,
            TenantMembership.user_id == user.id,
        ).first()
        if membership is None:
            db.add(TenantMembership(
                tenant_id=tenant.id,
                user_id=user.id,
                role_id=owner_role.id,
                status="active",
            ))
        else:
            membership.role_id = owner_role.id
            membership.status = "active"

        onboarding = db.query(TenantOnboarding).filter(
            TenantOnboarding.tenant_id == tenant.id
        ).first()
        if onboarding is None:
            db.add(TenantOnboarding.create_default(tenant.id))

        ConciergeEnrichmentService(db).ensure_started(tenant, user)
        db.commit()
        print(json.dumps({
            "email": email,
            "tenant_id": str(tenant.id),
            "created": created,
        }))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"Smoke account provisioning failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
