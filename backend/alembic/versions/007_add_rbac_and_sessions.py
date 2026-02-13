"""Add RBAC tables, sessions, and feature flags

Revision ID: 007
Revises: 006
Create Date: 2026-02-01
"""

from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Permissions table
    op.create_table(
        'permissions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now())
    )
    op.create_index('ix_permissions_key', 'permissions', ['key'], unique=True)

    # Roles table
    op.create_table(
        'roles',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('is_system', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now())
    )
    op.create_index('ix_roles_name', 'roles', ['name'], unique=True)

    # Role permissions association
    op.create_table(
        'role_permissions',
        sa.Column('role_id', sa.UUID(), sa.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_id', sa.UUID(), sa.ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True)
    )

    # Tenant memberships
    op.create_table(
        'tenant_memberships',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role_id', sa.UUID(), sa.ForeignKey('roles.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now())
    )
    op.create_index('ix_tenant_memberships_tenant_id', 'tenant_memberships', ['tenant_id'])
    op.create_index('ix_tenant_memberships_user_id', 'tenant_memberships', ['user_id'])
    op.create_index('ix_tenant_memberships_role_id', 'tenant_memberships', ['role_id'])
    op.create_unique_constraint('uq_tenant_membership', 'tenant_memberships', ['tenant_id', 'user_id'])

    # User sessions
    op.create_table(
        'user_sessions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('refresh_token_hash', sa.String(128), nullable=False),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('last_used_at', sa.DateTime, nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('revoked_at', sa.DateTime, nullable=True)
    )
    op.create_index('ix_user_sessions_user_id', 'user_sessions', ['user_id'])
    op.create_index('ix_user_sessions_refresh_token_hash', 'user_sessions', ['refresh_token_hash'])

    # Feature flags
    op.create_table(
        'feature_flags',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('tenant_id', sa.UUID(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('enabled', sa.Boolean, nullable=False, server_default='1'),
        sa.Column('payload_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now())
    )
    op.create_index('ix_feature_flags_tenant_id', 'feature_flags', ['tenant_id'])
    op.create_index('ix_feature_flags_key', 'feature_flags', ['key'])
    op.create_unique_constraint('uq_feature_flags_tenant_key', 'feature_flags', ['tenant_id', 'key'])

    # Seed permissions and roles
    permissions = [
        "tools:read",
        "tools:install",
        "dashboard:edit",
        "tickets:create",
        "tickets:manage",
        "team:invite",
        "settings:write",
        "audit:read",
        "automations:read",
        "automations:manage",
        "kyc:submit",
        "kyc:review",
        "users:read",
        "users:write"
    ]
    roles = {
        "owner": permissions,
        "admin": permissions,
        "manager": [
            "tools:read",
            "tools:install",
            "dashboard:edit",
            "tickets:create",
            "tickets:manage",
            "team:invite",
            "settings:write",
            "audit:read",
            "automations:read",
            "automations:manage",
            "kyc:submit",
            "users:read"
        ],
        "agent": [
            "tools:read",
            "dashboard:edit",
            "tickets:create",
            "tickets:manage",
            "automations:read",
            "kyc:submit"
        ],
        "viewer": [
            "tools:read",
            "automations:read"
        ],
        "system_admin": permissions
    }

    permissions_table = sa.table(
        'permissions',
        sa.column('id', sa.UUID),
        sa.column('key', sa.String),
        sa.column('description', sa.String)
    )
    roles_table = sa.table(
        'roles',
        sa.column('id', sa.UUID),
        sa.column('name', sa.String),
        sa.column('description', sa.String),
        sa.column('is_system', sa.Boolean)
    )
    role_permissions_table = sa.table(
        'role_permissions',
        sa.column('role_id', sa.UUID),
        sa.column('permission_id', sa.UUID)
    )

    permission_ids = {key: uuid4() for key in permissions}
    role_ids = {name: uuid4() for name in roles.keys()}

    op.bulk_insert(
        permissions_table,
        [{"id": pid, "key": key, "description": None} for key, pid in permission_ids.items()]
    )
    op.bulk_insert(
        roles_table,
        [{
            "id": rid,
            "name": name,
            "description": None,
            "is_system": name == "system_admin"
        } for name, rid in role_ids.items()]
    )
    role_permission_rows = []
    for role_name, perms in roles.items():
        for perm_key in perms:
            role_permission_rows.append({
                "role_id": role_ids[role_name],
                "permission_id": permission_ids[perm_key]
            })
    op.bulk_insert(role_permissions_table, role_permission_rows)

    # Seed owner memberships for existing tenants
    conn = op.get_bind()
    tenants = conn.execute(sa.text("SELECT id, owner_id FROM tenants")).fetchall()
    if tenants:
        memberships_table = sa.table(
            'tenant_memberships',
            sa.column('id', sa.UUID),
            sa.column('tenant_id', sa.UUID),
            sa.column('user_id', sa.UUID),
            sa.column('role_id', sa.UUID),
            sa.column('status', sa.String)
        )
        owner_role_id = role_ids["owner"]
        op.bulk_insert(
            memberships_table,
            [{
                "id": uuid4(),
                "tenant_id": tenant_id,
                "user_id": owner_id,
                "role_id": owner_role_id,
                "status": "active"
            } for tenant_id, owner_id in tenants]
        )


def downgrade() -> None:
    op.drop_index('ix_feature_flags_key', table_name='feature_flags')
    op.drop_index('ix_feature_flags_tenant_id', table_name='feature_flags')
    op.drop_constraint('uq_feature_flags_tenant_key', 'feature_flags', type_='unique')
    op.drop_table('feature_flags')

    op.drop_index('ix_user_sessions_refresh_token_hash', table_name='user_sessions')
    op.drop_index('ix_user_sessions_user_id', table_name='user_sessions')
    op.drop_table('user_sessions')

    op.drop_constraint('uq_tenant_membership', 'tenant_memberships', type_='unique')
    op.drop_index('ix_tenant_memberships_role_id', table_name='tenant_memberships')
    op.drop_index('ix_tenant_memberships_user_id', table_name='tenant_memberships')
    op.drop_index('ix_tenant_memberships_tenant_id', table_name='tenant_memberships')
    op.drop_table('tenant_memberships')

    op.drop_table('role_permissions')
    op.drop_index('ix_roles_name', table_name='roles')
    op.drop_table('roles')
    op.drop_index('ix_permissions_key', table_name='permissions')
    op.drop_table('permissions')
