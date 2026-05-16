from alembic import op
import sqlalchemy as sa


revision = "20260515_create_scheduler_runtime_observability_tables"
down_revision = "20260514_create_binance_exit_protection_transition_claims"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in set(inspector.get_table_names(schema="public"))


def _index_exists(bind, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(
        index.get("name") == index_name
        for index in inspector.get_indexes(table_name, schema="public")
    )


def upgrade():
    bind = op.get_bind()

    if not _table_exists(bind, "scheduler_runtime_state"):
        op.create_table(
            "scheduler_runtime_state",
            sa.Column("scheduler_name", sa.String(), primary_key=True, nullable=False),
            sa.Column("last_tick_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_tick_status", sa.String(), nullable=False, server_default="UNKNOWN"),
            sa.Column("last_tick_duration_ms", sa.Integer(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("overlap_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("runtime_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("trading_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("last_candidate_symbol", sa.String(), nullable=True),
            sa.Column("last_candidate_score", sa.String(), nullable=True),
            sa.Column("last_execution_mode", sa.String(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    if not _table_exists(bind, "scheduler_tick_journal"):
        op.create_table(
            "scheduler_tick_journal",
            sa.Column("tick_id", sa.String(), primary_key=True, nullable=False),
            sa.Column("scheduler_name", sa.String(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("duration_ms", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("overlap_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("runtime_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("trading_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("candidate_symbol", sa.String(), nullable=True),
            sa.Column("candidate_score", sa.String(), nullable=True),
            sa.Column("execution_mode", sa.String(), nullable=True),
            sa.Column("mutation_attempted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("mutation_executed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    if _table_exists(bind, "scheduler_tick_journal"):
        if not _index_exists(bind, "scheduler_tick_journal", "ix_scheduler_tick_journal_scheduler_name"):
            op.create_index(
                "ix_scheduler_tick_journal_scheduler_name",
                "scheduler_tick_journal",
                ["scheduler_name"],
            )
        if not _index_exists(bind, "scheduler_tick_journal", "ix_scheduler_tick_journal_status"):
            op.create_index(
                "ix_scheduler_tick_journal_status",
                "scheduler_tick_journal",
                ["status"],
            )


def downgrade():
    bind = op.get_bind()

    if _table_exists(bind, "scheduler_tick_journal"):
        if _index_exists(bind, "scheduler_tick_journal", "ix_scheduler_tick_journal_status"):
            op.drop_index("ix_scheduler_tick_journal_status", table_name="scheduler_tick_journal")
        if _index_exists(bind, "scheduler_tick_journal", "ix_scheduler_tick_journal_scheduler_name"):
            op.drop_index("ix_scheduler_tick_journal_scheduler_name", table_name="scheduler_tick_journal")
        op.drop_table("scheduler_tick_journal")

    if _table_exists(bind, "scheduler_runtime_state"):
        op.drop_table("scheduler_runtime_state")
