from alembic import op
import sqlalchemy as sa


revision = "20260518_add_scheduler_runtime_ownership_fields"
down_revision = "20260515_create_scheduler_runtime_observability_tables"
branch_labels = None
depends_on = None


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name, schema="public")
    return any(column.get("name") == column_name for column in columns)


def upgrade():
    bind = op.get_bind()

    ownership_columns = [
        (
            "runtime_owner_id",
            sa.Column("runtime_owner_id", sa.String(), nullable=True),
        ),
        (
            "runtime_instance_id",
            sa.Column("runtime_instance_id", sa.String(), nullable=True),
        ),
        (
            "runtime_generation",
            sa.Column("runtime_generation", sa.Integer(), nullable=True),
        ),
        (
            "runtime_started_at",
            sa.Column("runtime_started_at", sa.DateTime(timezone=True), nullable=True),
        ),
        (
            "runtime_heartbeat_at",
            sa.Column("runtime_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        ),
    ]

    for column_name, column in ownership_columns:
        if not _column_exists(bind, "scheduler_runtime_state", column_name):
            op.add_column("scheduler_runtime_state", column)


def downgrade():
    bind = op.get_bind()

    ownership_column_names = [
        "runtime_heartbeat_at",
        "runtime_started_at",
        "runtime_generation",
        "runtime_instance_id",
        "runtime_owner_id",
    ]

    for column_name in ownership_column_names:
        if _column_exists(bind, "scheduler_runtime_state", column_name):
            op.drop_column("scheduler_runtime_state", column_name)
