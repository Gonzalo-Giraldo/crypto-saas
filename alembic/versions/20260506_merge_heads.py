"""merge heads for exit protections

Revision ID: 20260506_merge_heads
Revises: 20260425_add_intent_financial_snapshot, 20260505_create_binance_exit_protections
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = "20260506_merge_heads"
down_revision = (
    "20260425_add_intent_financial_snapshot",
    "20260505_create_binance_exit_protections",
)
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
