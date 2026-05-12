"""restore positions table idempotently

Revision ID: 20260512_restore_positions_table_idempotent
Revises: 20260512_restore_intents_table_idempotent
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa


revision = "20260512_restore_positions_table_idempotent"
down_revision = "20260512_restore_intents_table_idempotent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "positions",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("signal_id", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("side", sa.String(), nullable=False, server_default="LONG"),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column("take_profit", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="OPEN"),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("realized_pnl", sa.Float(), nullable=True),
        sa.Column("fees", sa.Float(), nullable=True),
        if_not_exists=True,
    )
    op.create_index("ix_positions_user_id", "positions", ["user_id"], if_not_exists=True)
    op.create_index("ix_positions_signal_id", "positions", ["signal_id"], if_not_exists=True)
    op.create_index("ix_positions_symbol", "positions", ["symbol"], if_not_exists=True)
    op.create_index("ix_positions_status", "positions", ["status"], if_not_exists=True)


def downgrade() -> None:
    pass
