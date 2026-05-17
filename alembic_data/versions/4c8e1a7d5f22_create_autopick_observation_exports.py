"""create autopick observation exports

Revision ID: 4c8e1a7d5f22
Revises: 2a6f8d9c3b11
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa


revision = "4c8e1a7d5f22"
down_revision = "2a6f8d9c3b11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "autopick_observation_exports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("export_id", sa.String(length=64), nullable=False),
        sa.Column("from_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("to_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_count", sa.Integer(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("destination_kind", sa.String(length=32), nullable=False),
        sa.Column("destination_path_or_uri", sa.String(length=512), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("export_id"),
    )
    op.create_index("ix_data_autopick_export_id", "autopick_observation_exports", ["export_id"], unique=False)
    op.create_index("ix_data_autopick_export_status", "autopick_observation_exports", ["status"], unique=False)
    op.create_index("ix_data_autopick_export_window", "autopick_observation_exports", ["from_created_at", "to_created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_data_autopick_export_window", table_name="autopick_observation_exports")
    op.drop_index("ix_data_autopick_export_status", table_name="autopick_observation_exports")
    op.drop_index("ix_data_autopick_export_id", table_name="autopick_observation_exports")
    op.drop_table("autopick_observation_exports")
