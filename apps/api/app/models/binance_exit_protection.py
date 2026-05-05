from sqlalchemy import CheckConstraint, Column, DateTime, Integer, Numeric, String, Text, UniqueConstraint, func

from apps.api.app.db.session import Base


class BinanceExitProtection(Base):
    __tablename__ = "binance_exit_protections"

    id = Column(Integer, primary_key=True, nullable=False)
    exit_key = Column(String, nullable=False)
    intent_id = Column(String, nullable=False)
    entry_execution_ref = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    market = Column(String, nullable=False)
    direction = Column(String, nullable=False)
    filled_qty = Column(Numeric, nullable=False)
    avg_entry_price = Column(Numeric, nullable=False)

    sl_client_algo_id = Column(String, nullable=False)
    tp_client_algo_id = Column(String, nullable=False)
    sl_algo_id = Column(String, nullable=True)
    tp_algo_id = Column(String, nullable=True)

    sl_status = Column(String, nullable=False, default="PENDING")
    tp_status = Column(String, nullable=False, default="PENDING")
    protection_status = Column(String, nullable=False, default="UNPROTECTED")
    attempt_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("exit_key", name="uq_binance_exit_protections_exit_key"),
        CheckConstraint("market = 'FUTURES'", name="ck_binance_exit_protections_market_futures"),
        CheckConstraint("direction IN ('LONG', 'SHORT')", name="ck_binance_exit_protections_direction"),
        CheckConstraint("filled_qty > 0", name="ck_binance_exit_protections_filled_qty_positive"),
        CheckConstraint("avg_entry_price > 0", name="ck_binance_exit_protections_avg_entry_price_positive"),
        CheckConstraint(
            "sl_status IN ('PENDING', 'SUBMITTED', 'FAILED', 'CANCELED', 'TRIGGERED', 'UNKNOWN')",
            name="ck_binance_exit_protections_sl_status",
        ),
        CheckConstraint(
            "tp_status IN ('PENDING', 'SUBMITTED', 'FAILED', 'CANCELED', 'TRIGGERED', 'UNKNOWN')",
            name="ck_binance_exit_protections_tp_status",
        ),
        CheckConstraint(
            "protection_status IN ('UNPROTECTED', 'PARTIALLY_PROTECTED', 'PROTECTED', 'FAILED', 'UNKNOWN')",
            name="ck_binance_exit_protections_protection_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_binance_exit_protections_attempt_count_nonnegative"),
    )
