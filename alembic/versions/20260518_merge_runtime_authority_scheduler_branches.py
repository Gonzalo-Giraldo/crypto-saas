"""merge runtime authority scheduler branches

Revision ID: 20260518_merge_runtime_authority_scheduler_branches
Revises: 20260516_extend_scheduler_tick_journal_autopick_observation, 20260518_add_scheduler_runtime_generation_counter
Create Date: 2026-05-18
"""

revision = "20260518_merge_runtime_authority_scheduler_branches"
down_revision = (
    "20260516_extend_scheduler_tick_journal_autopick_observation",
    "20260518_add_scheduler_runtime_generation_counter",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
