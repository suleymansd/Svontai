"""
RBAC service for managing roles and permissions.
"""

from sqlalchemy.orm import Session

from app.core.permissions import PERMISSIONS, ROLE_PERMISSIONS, ROLE_DESCRIPTIONS
from app.models.permission import Permission
from app.models.role import Role


class RbacService:
    """Service for RBAC operations."""

    def __init__(self, db: Session):
        self.db = db

    def ensure_defaults(self) -> None:
        """Ensure default permissions and roles exist."""
        self._ensure_permissions()
        self._ensure_roles()
        self._ensure_role_permissions()

    def _ensure_permissions(self) -> None:
        existing = {
            perm.key: perm
            for perm in self.db.query(Permission).all()
        }
        for key in PERMISSIONS:
            if key not in existing:
                self.db.add(Permission(key=key))
        self.db.commit()

    def _ensure_roles(self) -> None:
        existing = {
            role.name: role
            for role in self.db.query(Role).all()
        }
        for role_name in ROLE_PERMISSIONS.keys():
            if role_name not in existing:
                self.db.add(
                    Role(
                        name=role_name,
                        description=ROLE_DESCRIPTIONS.get(role_name),
                        is_system=role_name == "system_admin"
                    )
                )
        self.db.commit()

    def _ensure_role_permissions(self) -> None:
        role_map = {
            role.name: role
            for role in self.db.query(Role).all()
        }
        perm_map = {
            perm.key: perm
            for perm in self.db.query(Permission).all()
        }

        updated = False
        for role_name, permissions in ROLE_PERMISSIONS.items():
            role = role_map.get(role_name)
            if not role:
                continue
            for perm_key in permissions:
                perm = perm_map.get(perm_key)
                if perm and perm not in role.permissions:
                    role.permissions.append(perm)
                    updated = True

        if updated:
            self.db.commit()

    def get_role_by_name(self, name: str) -> Role | None:
        """Fetch a role by name."""
        return self.db.query(Role).filter(Role.name == name).first()
