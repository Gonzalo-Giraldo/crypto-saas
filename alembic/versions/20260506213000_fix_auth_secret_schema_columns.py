"""fix auth secret schema columns

Revision ID: 20260506_fix_auth_secret_schema_columns
Revises: 20260506_restore_auth_secret_tables
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260506_fix_auth_secret_schema_columns"
down_revision = "20260506_restore_auth_secret_tables"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "users" in existing_tables:
        if not _has_column(inspector, "users", "hashed_password"):
            op.add_column(
                "users",
                sa.Column("hashed_password", sa.String(), nullable=True),
            )

        if not _has_column(inspector, "users", "password_changed_at"):
            op.add_column(
                "users",
                sa.Column(
                    "password_changed_at",
                    sa.DateTime(timezone=True),
                    nullable=False,
                    server_default=sa.func.now(),
                ),
            )

    if "user_two_factor" in existing_tables:
        if not _has_column(inspector, "user_two_factor", "secret"):
            op.add_column(
                "user_two_factor",
                sa.Column("secret", sa.String(), nullable=True),
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "user_two_factor" in existing_tables and _has_column(inspector, "user_two_factor", "secret"):
        op.drop_column("user_two_factor", "secret")

    if "users" in existing_tables and _has_column(inspector, "users", "password_changed_at"):
        op.drop_column("users", "password_changed_at")

    if "users" in existing_tables and _has_column(inspector, "users", "hashed_password"):
        op.drop_column("users", "hashed_password")
