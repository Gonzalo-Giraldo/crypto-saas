"""
Revision ID: 20260328_create_ibkr_fills_table
Revises: 20260327_add_symbol_to_intent_consumptions
Create Date: 2026-03-28
Create ibkr_fills table
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260328_create_ibkr_fills_table'
down_revision = '20260327_add_symbol_to_intent_consumptions'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'ibkr_fills'
            ) THEN
                CREATE TABLE ibkr_fills (
                    fill_id VARCHAR PRIMARY KEY,
                    execution_ref VARCHAR NOT NULL,
                    symbol VARCHAR NOT NULL,
                    qty FLOAT NOT NULL,
                    price FLOAT NOT NULL,
                    timestamp VARCHAR NOT NULL,
                    user_id VARCHAR NOT NULL,
                    broker VARCHAR NOT NULL
                );
            END IF;
        END
        $$;
    """)

def downgrade():
    op.drop_table('ibkr_fills')
