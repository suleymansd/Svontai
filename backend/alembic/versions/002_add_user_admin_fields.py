"""Add is_admin, is_active, last_login to users

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_admin column
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'))
    
    # Add is_active column
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    
    # Add last_login column
    op.add_column('users', sa.Column('last_login', sa.DateTime(), nullable=True))
    
    # Add slug column to tenants
    op.add_column('tenants', sa.Column('slug', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('tenants', 'slug')
    op.drop_column('users', 'last_login')
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'is_admin')

