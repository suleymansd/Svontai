"""Replace legacy robotic fallback and handoff defaults.

Revision ID: 051
Revises: 050
"""

from alembic import op
import sqlalchemy as sa


revision = "051"
down_revision = "050"
branch_labels = None
depends_on = None


NEW_FALLBACK = "Bu konuda yardımcı olamam; işletmemizle ilgili başka bir konuda yardımcı olabilirim."
NEW_HANDOFF = "Talebinizi ekibimize aktardım. Mümkün olan en kısa sürede sizinle ilgilenecekler."


def upgrade() -> None:
    with op.batch_alter_table("bot_settings") as batch_op:
        batch_op.alter_column(
            "fallback_message",
            existing_type=sa.Text(),
            existing_nullable=False,
            server_default=NEW_FALLBACK,
        )
        batch_op.alter_column(
            "human_handoff_message",
            existing_type=sa.Text(),
            existing_nullable=False,
            server_default=NEW_HANDOFF,
        )
    op.execute(
        sa.text(
            """
            UPDATE bot_settings
            SET fallback_message = :new_value
            WHERE fallback_message IN (
                'Üzgünüm, bu konuda size yardımcı olamıyorum.',
                'Üzgünüm, bu konuda size yardımcı olamıyorum. Lütfen bizimle iletişime geçin.'
            )
            """
        ).bindparams(new_value=NEW_FALLBACK)
    )
    op.execute(
        sa.text(
            """
            UPDATE bot_settings
            SET human_handoff_message = :new_value
            WHERE human_handoff_message IN (
                'Sizi bir müşteri temsilcimize bağlıyorum.',
                'Sizi bir müşteri temsilcimize bağlıyorum. Lütfen bekleyin.'
            )
            """
        ).bindparams(new_value=NEW_HANDOFF)
    )


def downgrade() -> None:
    old_fallback = "Üzgünüm, bu konuda size yardımcı olamıyorum. Lütfen bizimle iletişime geçin."
    old_handoff = "Sizi bir müşteri temsilcimize bağlıyorum. Lütfen bekleyin."
    op.execute(
        sa.text(
            "UPDATE bot_settings SET fallback_message = :old_value WHERE fallback_message = :new_value"
        ).bindparams(old_value=old_fallback, new_value=NEW_FALLBACK)
    )
    op.execute(
        sa.text(
            "UPDATE bot_settings SET human_handoff_message = :old_value WHERE human_handoff_message = :new_value"
        ).bindparams(old_value=old_handoff, new_value=NEW_HANDOFF)
    )
    with op.batch_alter_table("bot_settings") as batch_op:
        batch_op.alter_column(
            "fallback_message",
            existing_type=sa.Text(),
            existing_nullable=False,
            server_default=old_fallback,
        )
        batch_op.alter_column(
            "human_handoff_message",
            existing_type=sa.Text(),
            existing_nullable=False,
            server_default=old_handoff,
        )
