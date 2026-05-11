"""create runtime settings table

Revision ID: 20260511_create_runtime_settings
Revises: 20260507_restore_auth_audit_runtime_tables
Create Date: 2026-05-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260511_create_runtime_settings"
down_revision = "20260507_restore_auth_audit_runtime_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_settings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("bool_value", sa.Boolean(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_runtime_settings_key"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_runtime_settings_key",
        "runtime_settings",
        ["key"],
        unique=True,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_runtime_settings_key", table_name="runtime_settings", if_exists=True)
    op.drop_table("runtime_settings", if_exists=True)
