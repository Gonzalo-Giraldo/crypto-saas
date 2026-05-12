"""restore idempotency_keys table idempotently

Revision ID: 20260512_restore_idempotency_keys_table_idempotent
Revises: 20260512_restore_positions_table_idempotent
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa


revision = "20260512_restore_idempotency_keys_table_idempotent"
down_revision = "20260512_restore_positions_table_idempotent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("request_hash", sa.String(), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False, server_default="200"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id",
            "endpoint",
            "key_hash",
            name="uq_idempotency_user_endpoint_key",
        ),
        if_not_exists=True,
    )

    op.create_index(
        "ix_idempotency_keys_user_id",
        "idempotency_keys",
        ["user_id"],
        if_not_exists=True,
    )

    op.create_index(
        "ix_idempotency_keys_endpoint",
        "idempotency_keys",
        ["endpoint"],
        if_not_exists=True,
    )

    op.create_index(
        "ix_idempotency_keys_key_hash",
        "idempotency_keys",
        ["key_hash"],
        if_not_exists=True,
    )

    op.create_index(
        "ix_idempotency_keys_request_hash",
        "idempotency_keys",
        ["request_hash"],
        if_not_exists=True,
    )


def downgrade() -> None:
    pass
