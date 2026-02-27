"""Add agent_router tool seed record

Revision ID: 033
Revises: 032
Create Date: 2026-02-27
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tool_exists(bind) -> bool:
    return bool(
        bind.execute(
            sa.text(
                """
                SELECT 1
                FROM tools
                WHERE key = :key OR slug = :slug
                LIMIT 1
                """
            ),
            {"key": "agent_router", "slug": "agent_router"},
        ).scalar()
    )


def upgrade() -> None:
    bind = op.get_bind()

    if _tool_exists(bind):
        return

    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "context": {"type": "object"},
        },
        "required": ["text"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "selected_tool": {"type": "string"},
            "arguments": {"type": "object"},
            "confidence": {"type": "number"},
        },
        "required": ["summary"],
    }

    insert_stmt = sa.text(
        """
        INSERT INTO tools (
            id,
            key,
            slug,
            name,
            description,
            category,
            status,
            is_public,
            coming_soon,
            is_premium,
            required_plan,
            required_integrations_json,
            n8n_workflow_id,
            input_schema_json,
            output_schema_json,
            tags,
            created_at,
            updated_at
        )
        VALUES (
            :id,
            :key,
            :slug,
            :name,
            :description,
            :category,
            :status,
            :is_public,
            :coming_soon,
            :is_premium,
            :required_plan,
            :required_integrations_json,
            :n8n_workflow_id,
            :input_schema_json,
            :output_schema_json,
            :tags,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )
        """
    ).bindparams(
        sa.bindparam("required_integrations_json", type_=sa.JSON()),
        sa.bindparam("input_schema_json", type_=sa.JSON()),
        sa.bindparam("output_schema_json", type_=sa.JSON()),
        sa.bindparam("tags", type_=sa.JSON()),
    )

    bind.execute(
        insert_stmt,
        {
            "id": str(uuid.uuid4()),
            "key": "agent_router",
            "slug": "agent_router",
            "name": "Agent Router",
            "description": "Kullanıcı isteğine göre tool seçimi yapan yönlendirici (Agent Mode).",
            "category": "agent",
            "status": "active",
            "is_public": True,
            "coming_soon": False,
            "is_premium": False,
            "required_plan": "free",
            "required_integrations_json": ["openai"],
            "n8n_workflow_id": "svontai-tool-runner",
            "input_schema_json": input_schema,
            "output_schema_json": output_schema,
            "tags": [],
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            DELETE FROM tools
            WHERE key = :key OR slug = :slug
            """
        ),
        {"key": "agent_router", "slug": "agent_router"},
    )
