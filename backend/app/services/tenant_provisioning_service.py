"""Idempotent tenant provisioning for verified users."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.tenant_membership import TenantMembership
from app.models.user import User
from app.services.rbac_service import RbacService
from app.services.system_event_service import SystemEventService


class TenantProvisioningService:
    """Repair users whose registration completed without a tenant."""

    def __init__(self, db: Session):
        self.db = db

    def find_for_user(self, user: User) -> Tenant | None:
        owned = self.db.query(Tenant).filter(Tenant.owner_id == user.id).first()
        if owned:
            return owned

        membership = self.db.query(TenantMembership).filter(
            TenantMembership.user_id == user.id,
            TenantMembership.status == "active",
        ).first()
        return membership.tenant if membership else None

    def ensure_for_user(self, user: User) -> Tenant:
        existing = self.find_for_user(user)
        if existing:
            return existing

        rbac = RbacService(self.db)
        rbac.ensure_defaults()
        owner_role = rbac.get_role_by_name("owner")
        if owner_role is None:
            raise RuntimeError("Owner role is not configured")

        # Serialize first-tenant creation for the same user on PostgreSQL.
        locked_user = self.db.query(User).filter(User.id == user.id).with_for_update().one()
        existing = self.find_for_user(locked_user)
        if existing:
            self.db.commit()
            return existing

        display_name = (locked_user.full_name or locked_user.email.split("@", 1)[0]).strip()
        tenant = Tenant(
            name=f"{display_name} İşletmesi",
            owner_id=locked_user.id,
            settings={"provisioning_source": "login_repair"},
        )
        self.db.add(tenant)
        self.db.flush()
        self.db.add(
            TenantMembership(
                tenant_id=tenant.id,
                user_id=locked_user.id,
                role_id=owner_role.id,
                status="active",
            )
        )
        self.db.commit()
        self.db.refresh(tenant)

        SystemEventService(self.db).log(
            tenant_id=str(tenant.id),
            source="auth",
            level="info",
            code="TENANT_AUTO_PROVISIONED",
            message="Eksik işletme kaydı giriş sırasında otomatik oluşturuldu.",
            meta_json={"user_id": str(locked_user.id)},
        )
        return tenant
