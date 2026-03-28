"""
Revision ID: 20260323_add_key_version_to_exchange_secret
Revises: 20260322_create_binance_fills_table
Create Date: 2026-03-23
Adds key_version column to exchange_secret table.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260323_add_key_version_to_exchange_secret'
down_revision = '20260322_create_binance_fills_table'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column(
        'exchange_secret',
        sa.Column('key_version', sa.String(), nullable=False, server_default='v1')
    )
    op.create_index('ix_exchange_secret_key_version', 'exchange_secret', ['key_version'])

def downgrade():
    op.drop_index('ix_exchange_secret_key_version', table_name='exchange_secret')
    op.drop_column('exchange_secret', 'key_version')
