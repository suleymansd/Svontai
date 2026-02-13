"""
Permission dependencies for RBAC.
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, get_current_membership
from app.models.user import User
from app.models.tenant_membership import TenantMembership
from app.models.role import Role


def _get_permissions_for_role(role: Role) -> set[str]:
    return {perm.key for perm in role.permissions}


def require_permissions(required: list[str]):
    """Dependency factory to require permissions."""

    async def _dependency(
        current_user: User = Depends(get_current_user),
        membership: TenantMembership = Depends(get_current_membership),
        db: Session = Depends(get_db)
    ) -> None:
        if current_user.is_admin:
            return

        # Refresh only direct relationships; nested paths aren't supported by refresh()
        db.refresh(membership, ["role"])
        granted = _get_permissions_for_role(membership.role)
        missing = [perm for perm in required if perm not in granted]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu işlem için yetkiniz yok"
            )

    return _dependency
