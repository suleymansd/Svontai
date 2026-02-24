"""Fix tools.id type mismatch (text -> uuid)

Revision ID: 032
Revises: 031
Create Date: 2026-02-24
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID_REGEX = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"


def _is_postgres(bind) -> bool:
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    bind = op.get_bind()
    if not _is_postgres(bind):
        return

    inspector = sa.inspect(bind)
    columns = {column["name"]: column for column in inspector.get_columns("tools")}
    id_column = columns.get("id")
    if not id_column:
        return

    # If already UUID, nothing to do.
    if str(id_column.get("type", "")).lower() == "uuid":
        return

    # 1) Make all ids UUID-like before type conversion.
    invalid_rows = bind.execute(
        sa.text(
            f"""
            SELECT id
            FROM tools
            WHERE id IS NULL OR id !~ :uuid_regex
            """
        ),
        {"uuid_regex": UUID_REGEX},
    ).fetchall()

    for row in invalid_rows:
        old_id = row[0]
        bind.execute(
            sa.text("UPDATE tools SET id = :new_id WHERE id IS NOT DISTINCT FROM :old_id"),
            {"new_id": str(uuid.uuid4()), "old_id": old_id},
        )

    # 2) Ensure PK is sane before/after alter.
    pk_info = inspector.get_pk_constraint("tools") or {}
    pk_name = pk_info.get("name")
    pk_columns = pk_info.get("constrained_columns") or []
    if pk_columns and pk_columns != ["id"] and pk_name:
        op.drop_constraint(pk_name, "tools", type_="primary")

    # 3) Convert tools.id from text/varchar to uuid.
    op.execute("ALTER TABLE tools ALTER COLUMN id TYPE uuid USING id::uuid")

    # 4) Recreate PK if missing or wrong.
    inspector = sa.inspect(bind)
    pk_info = inspector.get_pk_constraint("tools") or {}
    pk_columns = pk_info.get("constrained_columns") or []
    if pk_columns != ["id"]:
        if pk_info.get("name"):
            op.drop_constraint(pk_info["name"], "tools", type_="primary")
        op.create_primary_key("tools_pkey", "tools", ["id"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _is_postgres(bind):
        return

    op.execute("ALTER TABLE tools ALTER COLUMN id TYPE text USING id::text")
