"""create binance exit protection transition claims

Revision ID: 20260514_create_binance_exit_protection_transition_claims
Revises: 20260512_restore_idempotency_keys_table_idempotent
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa


revision = "20260514_create_binance_exit_protection_transition_claims"
down_revision = "20260512_restore_idempotency_keys_table_idempotent"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "binance_exit_protection_transition_claims",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("exit_key", sa.String(), nullable=False),
        sa.Column("required_action", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("claim_status", sa.String(), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "claim_status IN ('ACTIVE', 'RELEASED', 'FINALIZED', 'ABANDONED')",
            name="ck_binance_exit_protection_transition_claim_status",
        ),
    )
    op.create_index(
        "uq_binance_exit_protection_transition_claim_active",
        "binance_exit_protection_transition_claims",
        ["exit_key", "required_action"],
        unique=True,
        postgresql_where=sa.text("claim_status = 'ACTIVE'"),
        sqlite_where=sa.text("claim_status = 'ACTIVE'"),
    )
    op.create_index(
        "ix_binance_exit_protection_transition_claims_exit_key",
        "binance_exit_protection_transition_claims",
        ["exit_key"],
    )
    op.create_index(
        "ix_binance_exit_protection_transition_claims_owner_status",
        "binance_exit_protection_transition_claims",
        ["owner_id", "claim_status"],
    )


def downgrade():
    op.drop_index(
        "ix_binance_exit_protection_transition_claims_owner_status",
        table_name="binance_exit_protection_transition_claims",
    )
    op.drop_index(
        "ix_binance_exit_protection_transition_claims_exit_key",
        table_name="binance_exit_protection_transition_claims",
    )
    op.drop_index(
        "uq_binance_exit_protection_transition_claim_active",
        table_name="binance_exit_protection_transition_claims",
    )
    op.drop_table("binance_exit_protection_transition_claims")
