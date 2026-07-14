"""Fix legacy conversation metadata schema drift.

Revision ID: 036
Revises: 035_add_voice_automation_tables
Create Date: 2026-07-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "036"
down_revision: Union[str, None] = "035_add_voice_automation_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns() -> set[str]:
    return {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("conversations")
    }


def _drop_column(name: str) -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("conversations") as batch_op:
            batch_op.drop_column(name)
        return
    op.drop_column("conversations", name)


def upgrade() -> None:
    columns = _columns()
    if "metadata" in columns and "extra_data" not in columns:
        op.alter_column("conversations", "metadata", new_column_name="extra_data")
    elif "metadata" in columns and "extra_data" in columns:
        conversations = sa.table(
            "conversations",
            sa.column("metadata", sa.JSON()),
            sa.column("extra_data", sa.JSON()),
        )
        op.get_bind().execute(
            conversations.update()
            .where(
                sa.and_(
                    conversations.c.metadata.is_not(None),
                    sa.or_(
                        conversations.c.extra_data.is_(None),
                        sa.cast(conversations.c.extra_data, sa.Text()) == "{}",
                    ),
                )
            )
            .values(extra_data=conversations.c.metadata)
        )
        _drop_column("metadata")
    elif "extra_data" not in columns:
        op.add_column(
            "conversations",
            sa.Column("extra_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        )

    if op.get_bind().dialect.name != "sqlite":
        op.alter_column(
            "conversations",
            "extra_data",
            existing_type=sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        )


def downgrade() -> None:
    columns = _columns()
    if "extra_data" in columns and "metadata" not in columns:
        op.alter_column("conversations", "extra_data", new_column_name="metadata")
    elif "extra_data" in columns and "metadata" in columns:
        conversations = sa.table(
            "conversations",
            sa.column("metadata", sa.JSON()),
            sa.column("extra_data", sa.JSON()),
        )
        op.get_bind().execute(
            conversations.update().values(metadata=conversations.c.extra_data)
        )
        _drop_column("extra_data")
