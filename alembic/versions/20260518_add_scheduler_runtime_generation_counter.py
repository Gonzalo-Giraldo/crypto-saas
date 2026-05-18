"""add scheduler runtime generation counter

Revision ID: 20260518_add_scheduler_runtime_generation_counter
Revises: 20260518_add_scheduler_runtime_ownership_fields
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa


revision = "20260518_add_scheduler_runtime_generation_counter"
down_revision = "20260518_add_scheduler_runtime_ownership_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scheduler_runtime_state",
        sa.Column(
            "last_runtime_generation",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("scheduler_runtime_state", "last_runtime_generation")
