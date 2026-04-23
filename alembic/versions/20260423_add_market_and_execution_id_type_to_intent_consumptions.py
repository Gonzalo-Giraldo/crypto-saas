"""add market and broker_execution_id_type to intent_consumptions

Revision ID: 20260423_add_market_and_execution_id_type_to_intent_consumptions
Revises: 20260327_add_symbol_to_intent_consumptions
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa

revision = "20260423_add_market_and_execution_id_type_to_intent_consumptions"
down_revision = "20260327_add_symbol_to_intent_consumptions"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("intent_consumptions", sa.Column("market", sa.String(), nullable=True))
    op.add_column("intent_consumptions", sa.Column("broker_execution_id_type", sa.String(), nullable=True))

def downgrade():
    op.drop_column("intent_consumptions", "broker_execution_id_type")
    op.drop_column("intent_consumptions", "market")
