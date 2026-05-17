from alembic import op
import sqlalchemy as sa


revision = "20260516_extend_scheduler_tick_journal_autopick_observation"
down_revision = "20260515_create_scheduler_runtime_observability_tables"
branch_labels = None
depends_on = None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(
        column.get("name") == column_name
        for column in inspector.get_columns(table_name, schema="public")
    )


def upgrade():
    bind = op.get_bind()

    if not _column_exists(bind, "scheduler_tick_journal", "decision_status"):
        op.add_column("scheduler_tick_journal", sa.Column("decision_status", sa.String(), nullable=True))

    if not _column_exists(bind, "scheduler_tick_journal", "selected_rank"):
        op.add_column("scheduler_tick_journal", sa.Column("selected_rank", sa.Integer(), nullable=True))

    if not _column_exists(bind, "scheduler_tick_journal", "ranked_count"):
        op.add_column("scheduler_tick_journal", sa.Column("ranked_count", sa.Integer(), nullable=True))

    if not _column_exists(bind, "scheduler_tick_journal", "top_n"):
        op.add_column("scheduler_tick_journal", sa.Column("top_n", sa.Integer(), nullable=True))

    if not _column_exists(bind, "scheduler_tick_journal", "observation_payload_json"):
        op.add_column("scheduler_tick_journal", sa.Column("observation_payload_json", sa.Text(), nullable=True))

    if not _column_exists(bind, "scheduler_tick_journal", "analytics_exported"):
        op.add_column(
            "scheduler_tick_journal",
            sa.Column("analytics_exported", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade():
    bind = op.get_bind()

    for column_name in (
        "analytics_exported",
        "observation_payload_json",
        "top_n",
        "ranked_count",
        "selected_rank",
        "decision_status",
    ):
        if _column_exists(bind, "scheduler_tick_journal", column_name):
            op.drop_column("scheduler_tick_journal", column_name)
