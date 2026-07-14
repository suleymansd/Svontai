"""
Upgrade all active owner/member tenants of a user to premium.

Run:
  python backend/scripts/upgrade_to_premium.py user@example.com
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import func


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal
from app.models.tenant import Tenant
from app.models.tenant_membership import TenantMembership
from app.models.user import User
from app.services.subscription_service import SubscriptionService


def _is_tenant_active(settings_json: dict | None) -> bool:
    if not isinstance(settings_json, dict):
        return True
    return not bool(settings_json.get("suspended"))


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python backend/scripts/upgrade_to_premium.py <email>")
        return 1

    email = (sys.argv[1] or "").strip().lower()
    if not email:
        print("USER_NOT_FOUND")
        return 1

    db = SessionLocal()
    try:
        user = db.query(User).filter(func.lower(User.email) == email).first()
        if not user:
            print("USER_NOT_FOUND")
            return 1

        tenant_ids: set[str] = set()

        owner_tenants = db.query(Tenant.id, Tenant.settings).filter(Tenant.owner_id == user.id).all()
        for tenant_id, tenant_settings in owner_tenants:
            if _is_tenant_active(tenant_settings):
                tenant_ids.add(str(tenant_id))

        membership_rows = (
            db.query(TenantMembership.tenant_id, Tenant.settings)
            .join(Tenant, Tenant.id == TenantMembership.tenant_id)
            .filter(
                TenantMembership.user_id == user.id,
                TenantMembership.status == "active",
            )
            .all()
        )
        for tenant_id, tenant_settings in membership_rows:
            if _is_tenant_active(tenant_settings):
                tenant_ids.add(str(tenant_id))

        if not tenant_ids:
            print("TENANT_NOT_FOUND")
            return 1

        service = SubscriptionService(db)
        for tenant_id in sorted(tenant_ids):
            service.upgrade_plan(tenant_id=UUID(tenant_id), new_plan_name="premium")
            print(f"UPDATED {tenant_id} -> premium")

        db.commit()
        return 0
    except Exception as exc:
        db.rollback()
        print(f"ERROR: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
