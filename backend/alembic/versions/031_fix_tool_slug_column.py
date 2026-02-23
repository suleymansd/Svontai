"""Ensure tools.slug exists and is non-null unique

Revision ID: 031
Revises: 030
Create Date: 2026-02-23
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    return {col["name"] for col in inspector.get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind, "tools")

    if "slug" not in columns:
        op.add_column("tools", sa.Column("slug", sa.String(length=120), nullable=True))

    op.execute("UPDATE tools SET slug = key WHERE slug IS NULL OR slug = ''")

    index_names = _index_names(bind, "tools")
    if "ix_tools_slug" not in index_names:
        op.create_index("ix_tools_slug", "tools", ["slug"], unique=True)

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("tools") as batch_op:
            batch_op.alter_column(
                "slug",
                existing_type=sa.String(length=120),
                nullable=False,
            )
    else:
        op.alter_column(
            "tools",
            "slug",
            existing_type=sa.String(length=120),
            nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("tools") as batch_op:
            batch_op.alter_column(
                "slug",
                existing_type=sa.String(length=120),
                nullable=True,
            )
    else:
        op.alter_column(
            "tools",
            "slug",
            existing_type=sa.String(length=120),
            nullable=True,
        )
