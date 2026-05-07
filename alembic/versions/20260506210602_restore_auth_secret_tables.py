"""restore auth secret tables

Revision ID: restore_auth_secret_tables
Revises:
Create Date: 2026-05-06

"""

from alembic import op
import sqlalchemy as sa


revision = "20260506_restore_auth_secret_tables"
down_revision = "20260506_merge_heads"
branch_labels = None
depends_on = None


def upgrade():

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = set(inspector.get_table_names())

    if "users" not in existing_tables:

        op.create_table(
            "users",

            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("role", sa.String(length=64), nullable=True),
            sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="default"),

            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),

            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),

            sa.UniqueConstraint(
                "email",
                name="uq_users_email",
            ),
        )

    if "user_two_factor" not in existing_tables:

        op.create_table(
            "user_two_factor",

            sa.Column(
                "user_id",
                sa.String(length=64),
                nullable=False,
            ),

            sa.Column(
                "enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),

            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),

            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),

            sa.PrimaryKeyConstraint(
                "user_id",
                name="pk_user_two_factor",
            ),
        )

    if "exchange_secret" not in existing_tables:

        op.create_table(
            "exchange_secret",

            sa.Column(
                "id",
                sa.String(length=64),
                primary_key=True,
            ),

            sa.Column(
                "user_id",
                sa.String(length=64),
                nullable=False,
            ),

            sa.Column(
                "exchange",
                sa.String(length=64),
                nullable=False,
            ),

            sa.Column(
                "api_key_encrypted",
                sa.Text(),
                nullable=False,
            ),

            sa.Column(
                "api_secret_encrypted",
                sa.Text(),
                nullable=False,
            ),

            sa.Column(
                "key_version",
                sa.String(length=64),
                nullable=False,
                server_default="v1",
            ),

            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),

            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),

            sa.UniqueConstraint(
                "user_id",
                "exchange",
                name="uq_exchange_secret_user_exchange",
            ),
        )


def downgrade():

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = set(inspector.get_table_names())

    if "exchange_secret" in existing_tables:
        op.drop_table("exchange_secret")

    if "user_two_factor" in existing_tables:
        op.drop_table("user_two_factor")

    if "users" in existing_tables:
        op.drop_table("users")
