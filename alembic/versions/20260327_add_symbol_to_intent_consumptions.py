"""
Revision ID: 20260327_add_symbol_to_intent_consumptions
Revises: 20260323_add_key_version_to_exchange_secret
Create Date: 2026-03-27
Add symbol column to intent_consumptions
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260327_add_symbol_to_intent_consumptions'
down_revision = '20260323_add_key_version_to_exchange_secret'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='intent_consumptions'
                AND column_name='symbol'
            ) THEN
                ALTER TABLE intent_consumptions ADD COLUMN symbol VARCHAR;
            END IF;
        END
        $$;
    """)

def downgrade():
    op.drop_column('intent_consumptions', 'symbol')
