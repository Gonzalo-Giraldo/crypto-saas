"""create binance_exit_protections table

Revision ID: 20260505_create_binance_exit_protections
Revises: 20260423_add_market_and_execution_id_type_to_intent_consumptions
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = "20260505_create_binance_exit_protections"
down_revision = "20260423_add_market_and_execution_id_type_to_intent_consumptions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "binance_exit_protections",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("exit_key", sa.String(), nullable=False),
        sa.Column("intent_id", sa.String(), nullable=False),
        sa.Column("entry_execution_ref", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("market", sa.String(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("filled_qty", sa.Numeric(), nullable=False),
        sa.Column("avg_entry_price", sa.Numeric(), nullable=False),
        sa.Column("sl_client_algo_id", sa.String(), nullable=False),
        sa.Column("tp_client_algo_id", sa.String(), nullable=False),
        sa.Column("sl_algo_id", sa.String(), nullable=True),
        sa.Column("tp_algo_id", sa.String(), nullable=True),
        sa.Column("sl_status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("tp_status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("protection_status", sa.String(), nullable=False, server_default="UNPROTECTED"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("exit_key", name="uq_binance_exit_protections_exit_key"),
        sa.CheckConstraint("market = 'FUTURES'", name="ck_binance_exit_protections_market_futures"),
        sa.CheckConstraint("direction IN ('LONG', 'SHORT')", name="ck_binance_exit_protections_direction"),
        sa.CheckConstraint("filled_qty > 0", name="ck_binance_exit_protections_filled_qty_positive"),
        sa.CheckConstraint("avg_entry_price > 0", name="ck_binance_exit_protections_avg_entry_price_positive"),
        sa.CheckConstraint(
            "sl_status IN ('PENDING', 'SUBMITTED', 'FAILED', 'CANCELED', 'TRIGGERED', 'UNKNOWN')",
            name="ck_binance_exit_protections_sl_status",
        ),
        sa.CheckConstraint(
            "tp_status IN ('PENDING', 'SUBMITTED', 'FAILED', 'CANCELED', 'TRIGGERED', 'UNKNOWN')",
            name="ck_binance_exit_protections_tp_status",
        ),
        sa.CheckConstraint(
            "protection_status IN ('UNPROTECTED', 'PARTIALLY_PROTECTED', 'PROTECTED', 'FAILED', 'UNKNOWN')",
            name="ck_binance_exit_protections_protection_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_binance_exit_protections_attempt_count_nonnegative"),
    )
    op.create_index(
        "ix_binance_exit_protections_intent_id",
        "binance_exit_protections",
        ["intent_id"],
    )
    op.create_index(
        "ix_binance_exit_protections_entry_execution_ref",
        "binance_exit_protections",
        ["entry_execution_ref"],
    )
    op.create_index(
        "ix_binance_exit_protections_symbol_status",
        "binance_exit_protections",
        ["symbol", "protection_status"],
    )


def downgrade():
    op.drop_index("ix_binance_exit_protections_symbol_status", table_name="binance_exit_protections")
    op.drop_index("ix_binance_exit_protections_entry_execution_ref", table_name="binance_exit_protections")
    op.drop_index("ix_binance_exit_protections_intent_id", table_name="binance_exit_protections")
    op.drop_table("binance_exit_protections")
