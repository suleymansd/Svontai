"""Reserve concurrent reply quota before external work.

Revision ID: 057
Revises: 056
"""

from alembic import op
import sqlalchemy as sa

revision = "057"
down_revision = "056"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_messages_sender_created", "messages", ["sender", "created_at"])
    op.create_table(
        "reply_reservations",
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_reply_reservation_tenant_period_state", "reply_reservations", ["tenant_id", "period", "state"])
    op.create_table(
        "operator_deliveries",
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempt_token", sa.String(32)),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "request_id", name="uq_operator_delivery_request"),
    )
    op.create_index("ix_operator_delivery_status_updated", "operator_deliveries", ["status", "updated_at"])
    op.create_index("ix_operator_delivery_tenant", "operator_deliveries", ["tenant_id"])


def downgrade():
    op.drop_index("ix_messages_sender_created", table_name="messages")
    op.drop_table("operator_deliveries")
    op.drop_table("reply_reservations")
