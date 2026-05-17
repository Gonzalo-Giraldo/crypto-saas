"""add autopick lineage columns

Revision ID: 9b4d2c1f0a77
Revises: 7f3d84039a6f
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa


revision = "9b4d2c1f0a77"
down_revision = "7f3d84039a6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "autopick_observation_snapshots",
        sa.Column(
            "model_version",
            sa.String(length=64),
            nullable=False,
            server_default="binance_auto_pick_pipeline_v1",
        ),
    )
    op.add_column(
        "autopick_observation_snapshots",
        sa.Column("selected_side", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "autopick_observation_snapshots",
        sa.Column("selected_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "autopick_observation_snapshots",
        sa.Column("selected_reason", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("autopick_observation_snapshots", "selected_reason")
    op.drop_column("autopick_observation_snapshots", "selected_score")
    op.drop_column("autopick_observation_snapshots", "selected_side")
    op.drop_column("autopick_observation_snapshots", "model_version")
