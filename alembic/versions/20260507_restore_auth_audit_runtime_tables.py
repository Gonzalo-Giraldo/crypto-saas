"""restore auth audit runtime tables

Revision ID: 20260507_restore_auth_audit_runtime_tables
Revises: 20260506_add_key_version_to_user_two_factor
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260507_restore_auth_audit_runtime_tables"
down_revision = "20260506_add_key_version_to_user_two_factor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_revocation",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "revoked_after",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id"),
        if_not_exists=True,
    )

    op.create_index(
        "ix_session_revocation_user_id",
        "session_revocation",
        ["user_id"],
        unique=False,
        if_not_exists=True,
    )

    op.create_table(
        "revoked_token",
        sa.Column("jti", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("token_type", sa.String(), nullable=False),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("jti"),
        if_not_exists=True,
    )

    op.create_index(
        "ix_revoked_token_jti",
        "revoked_token",
        ["jti"],
        unique=False,
        if_not_exists=True,
    )

    op.create_index(
        "ix_revoked_token_user_id",
        "revoked_token",
        ["user_id"],
        unique=False,
        if_not_exists=True,
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )

    op.create_index(
        "ix_audit_log_user_id",
        "audit_log",
        ["user_id"],
        unique=False,
        if_not_exists=True,
    )

    op.create_index(
        "ix_audit_log_action",
        "audit_log",
        ["action"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_audit_log_action",
        table_name="audit_log",
        if_exists=True,
    )

    op.drop_index(
        "ix_audit_log_user_id",
        table_name="audit_log",
        if_exists=True,
    )

    op.drop_table(
        "audit_log",
        if_exists=True,
    )

    op.drop_index(
        "ix_revoked_token_user_id",
        table_name="revoked_token",
        if_exists=True,
    )

    op.drop_index(
        "ix_revoked_token_jti",
        table_name="revoked_token",
        if_exists=True,
    )

    op.drop_table(
        "revoked_token",
        if_exists=True,
    )

    op.drop_index(
        "ix_session_revocation_user_id",
        table_name="session_revocation",
        if_exists=True,
    )

    op.drop_table(
        "session_revocation",
        if_exists=True,
    )
