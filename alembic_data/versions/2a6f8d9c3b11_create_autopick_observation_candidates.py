"""create autopick observation candidates

Revision ID: 2a6f8d9c3b11
Revises: 9b4d2c1f0a77
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa


revision = "2a6f8d9c3b11"
down_revision = "9b4d2c1f0a77"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "autopick_observation_candidates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("side", sa.String(length=16), nullable=True),
        sa.Column("valid", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(length=128), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("entry_price_reference", sa.Float(), nullable=True),
        sa.Column("features_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_autopick_candidate_snapshot_id", "autopick_observation_candidates", ["snapshot_id"], unique=False)
    op.create_index("ix_data_autopick_candidate_symbol", "autopick_observation_candidates", ["symbol"], unique=False)
    op.create_index("ix_data_autopick_candidate_rank", "autopick_observation_candidates", ["rank"], unique=False)
    op.create_index("ix_data_autopick_candidate_selected", "autopick_observation_candidates", ["selected"], unique=False)
    op.create_index("ix_data_autopick_candidate_created_at", "autopick_observation_candidates", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_data_autopick_candidate_created_at", table_name="autopick_observation_candidates")
    op.drop_index("ix_data_autopick_candidate_selected", table_name="autopick_observation_candidates")
    op.drop_index("ix_data_autopick_candidate_rank", table_name="autopick_observation_candidates")
    op.drop_index("ix_data_autopick_candidate_symbol", table_name="autopick_observation_candidates")
    op.drop_index("ix_data_autopick_candidate_snapshot_id", table_name="autopick_observation_candidates")
    op.drop_table("autopick_observation_candidates")
