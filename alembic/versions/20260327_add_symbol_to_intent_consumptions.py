"""
Add symbol column to intent_consumptions
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('intent_consumptions', sa.Column('symbol', sa.String(), nullable=True))

def downgrade():
    op.drop_column('intent_consumptions', 'symbol')
