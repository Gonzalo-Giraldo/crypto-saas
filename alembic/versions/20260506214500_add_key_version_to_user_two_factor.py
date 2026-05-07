"""add key version to user two factor

Revision ID: 20260506_add_key_version_to_user_two_factor
Revises: 20260506_fix_auth_secret_schema_columns
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260506_add_key_version_to_user_two_factor"
down_revision = "20260506_fix_auth_secret_schema_columns"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {c["name"] for c in inspector.get_columns(table_name)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "user_two_factor" in set(inspector.get_table_names()):
        if not _has_column(inspector, "user_two_factor", "key_version"):
            op.add_column(
                "user_two_factor",
                sa.Column(
                    "key_version",
                    sa.String(length=64),
                    nullable=False,
                    server_default="v1",
                ),
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if (
        "user_two_factor" in set(inspector.get_table_names())
        and _has_column(inspector, "user_two_factor", "key_version")
    ):
        op.drop_column("user_two_factor", "key_version")
