"""add normalized financial fields to binance_fills

Revision ID: 20260423_add_normalized_fields_to_binance_fills
Revises: 20260423_add_market_and_execution_id_type_to_intent_consumptions
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa

revision = "20260423_add_normalized_fields_to_binance_fills"
down_revision = "20260423_add_market_and_execution_id_type_to_intent_consumptions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("binance_fills", sa.Column("price", sa.Numeric(), nullable=True))
    op.add_column("binance_fills", sa.Column("qty", sa.Numeric(), nullable=True))
    op.add_column("binance_fills", sa.Column("quote_qty", sa.Numeric(), nullable=True))
    op.add_column("binance_fills", sa.Column("commission", sa.Numeric(), nullable=True))
    op.add_column("binance_fills", sa.Column("commission_asset", sa.String(), nullable=True))
    op.add_column("binance_fills", sa.Column("commission_price_usdt", sa.Numeric(), nullable=True))
    op.add_column("binance_fills", sa.Column("commission_usdt", sa.Numeric(), nullable=True))
    op.add_column("binance_fills", sa.Column("executed_at_ms", sa.BigInteger(), nullable=True))


def downgrade():
    op.drop_column("binance_fills", "executed_at_ms")
    op.drop_column("binance_fills", "commission_usdt")
    op.drop_column("binance_fills", "commission_price_usdt")
    op.drop_column("binance_fills", "commission_asset")
    op.drop_column("binance_fills", "commission")
    op.drop_column("binance_fills", "quote_qty")
    op.drop_column("binance_fills", "qty")
    op.drop_column("binance_fills", "price")
