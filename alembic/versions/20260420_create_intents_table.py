"""create intents table

Revision ID: 20260420_create_intents_table
Revises: 20260328_create_ibkr_fills_table
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa

revision = '20260420_create_intents_table'
down_revision = '20260328_create_ibkr_fills_table'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'intents',
        sa.Column('intent_id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=False, index=True),
        sa.Column('broker', sa.String(), nullable=False),
        sa.Column('account_id', sa.String(), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False, index=True),
        sa.Column('side', sa.String(), nullable=False),
        sa.Column('expected_qty', sa.Numeric(24, 8), nullable=False),
        sa.Column('order_type', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('lifecycle_status', sa.String(), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("side IN ('BUY', 'SELL')", name="ck_intent_side"),
        sa.CheckConstraint("expected_qty > 0", name="ck_intent_expected_qty_positive"),
        sa.CheckConstraint("broker IN ('BINANCE', 'IBKR')", name="ck_intent_broker"),
        sa.CheckConstraint(
            "lifecycle_status IN ('CREATED', 'CONSUMED', 'EXECUTED', 'PARTIALLY_FILLED', 'FILLED', 'FAILED', 'CANCELLED')",
            name="ck_intent_lifecycle_status",
        ),
    )
    op.create_index('ix_intent_user_id_created_at', 'intents', ['user_id', 'created_at'])
    op.create_index('ix_intent_broker_account_id_created_at', 'intents', ['broker', 'account_id', 'created_at'])
    op.create_index('ix_intent_lifecycle_status_created_at', 'intents', ['lifecycle_status', 'created_at'])
    op.create_index('ix_intent_symbol_created_at', 'intents', ['symbol', 'created_at'])

def downgrade():
    op.drop_index('ix_intent_symbol_created_at', table_name='intents')
    op.drop_index('ix_intent_lifecycle_status_created_at', table_name='intents')
    op.drop_index('ix_intent_broker_account_id_created_at', table_name='intents')
    op.drop_index('ix_intent_user_id_created_at', table_name='intents')
    op.drop_table('intents')
