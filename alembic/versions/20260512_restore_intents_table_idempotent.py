"""restore intents table idempotently

Revision ID: 20260512_restore_intents_table_idempotent
Revises: 20260511_create_runtime_settings
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260512_restore_intents_table_idempotent"
down_revision = "20260511_create_runtime_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intents",
        sa.Column("intent_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("broker", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("expected_qty", sa.Numeric(24, 8), nullable=False),
        sa.Column("entry_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("stop_loss", sa.Numeric(24, 8), nullable=True),
        sa.Column("take_profit", sa.Numeric(24, 8), nullable=True),
        sa.Column("strategy_id", sa.String(), nullable=True),
        sa.Column("risk_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("risk_abs", sa.Numeric(24, 8), nullable=True),
        sa.Column("policy_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("order_type", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("lifecycle_status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("side IN ('BUY', 'SELL')", name="ck_intent_side"),
        sa.CheckConstraint("expected_qty > 0", name="ck_intent_expected_qty_positive"),
        sa.CheckConstraint("broker IN ('BINANCE', 'IBKR')", name="ck_intent_broker"),
        sa.CheckConstraint(
            "lifecycle_status IN ('CREATED', 'CONSUMED', 'EXECUTED', 'PARTIALLY_FILLED', 'FILLED', 'FAILED', 'CANCELLED')",
            name="ck_intent_lifecycle_status",
        ),
        if_not_exists=True,
    )
    op.create_index("ix_intent_user_id_created_at", "intents", ["user_id", "created_at"], if_not_exists=True)
    op.create_index("ix_intent_broker_account_id_created_at", "intents", ["broker", "account_id", "created_at"], if_not_exists=True)
    op.create_index("ix_intent_lifecycle_status_created_at", "intents", ["lifecycle_status", "created_at"], if_not_exists=True)
    op.create_index("ix_intent_symbol_created_at", "intents", ["symbol", "created_at"], if_not_exists=True)


def downgrade() -> None:
    pass
