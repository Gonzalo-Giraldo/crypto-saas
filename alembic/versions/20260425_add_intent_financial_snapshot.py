"""add financial snapshot fields to intents

Revision ID: 20260425_add_intent_financial_snapshot
Revises: 20260424_add_realized_pnl_to_binance_fills
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260425_add_intent_financial_snapshot"
down_revision = "20260424_add_realized_pnl_to_binance_fills"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("intents", sa.Column("strategy_id", sa.String(), nullable=True))
    op.add_column("intents", sa.Column("risk_pct", sa.Numeric(10, 4), nullable=True))
    op.add_column("intents", sa.Column("risk_abs", sa.Numeric(24, 8), nullable=True))
    op.add_column("intents", sa.Column("policy_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column("intents", "policy_snapshot")
    op.drop_column("intents", "risk_abs")
    op.drop_column("intents", "risk_pct")
    op.drop_column("intents", "strategy_id")
