"""add realized_pnl to binance_fills

Revision ID: 20260424_add_realized_pnl_to_binance_fills
Revises: 20260423_add_normalized_fields_to_binance_fills
Create Date: 2026-04-24
"""
from alembic import op
import sqlalchemy as sa

revision = "20260424_add_realized_pnl_to_binance_fills"
down_revision = "20260423_add_normalized_fields_to_binance_fills"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("binance_fills", sa.Column("realized_pnl", sa.Numeric(), nullable=True))


def downgrade():
    op.drop_column("binance_fills", "realized_pnl")
