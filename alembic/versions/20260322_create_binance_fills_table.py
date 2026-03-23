"""
Revision ID: 20260322_create_binance_fills_table
Revises: 
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260322_create_binance_fills_table'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'binance_fills',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String, nullable=False),
        sa.Column('account_id', sa.String, nullable=False),
        sa.Column('broker', sa.String, nullable=False),
        sa.Column('market', sa.String, nullable=False),
        sa.Column('trade_id', sa.String, nullable=False),
        sa.Column('order_id', sa.String, nullable=True),
        sa.Column('symbol', sa.String, nullable=True),
        sa.Column('side', sa.String, nullable=True),
        sa.Column('raw_payload', sa.JSON, nullable=True),
        sa.UniqueConstraint(
            'user_id', 'account_id', 'broker', 'market', 'trade_id',
            name='uq_binance_fill_identity'
        ),
    )

def downgrade():
    op.drop_table('binance_fills')
