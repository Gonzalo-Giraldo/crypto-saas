import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, String, UniqueConstraint, func

from apps.api.app.db.session import Base


class StrategyRuntimePolicy(Base):
    __tablename__ = "strategy_runtime_policy"
    __table_args__ = (
        UniqueConstraint("strategy_id", "exchange", name="uq_runtime_policy_strategy_exchange"),
    )

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    strategy_id = Column(String, nullable=False, index=True)
    exchange = Column(String, nullable=False, index=True)

    allow_bull = Column(Boolean, nullable=False, default=True)
    allow_bear = Column(Boolean, nullable=False, default=True)
    allow_range = Column(Boolean, nullable=False, default=False)

    rr_min_bull = Column(Float, nullable=False, default=1.5)
    rr_min_bear = Column(Float, nullable=False, default=1.6)
    rr_min_range = Column(Float, nullable=False, default=1.8)
    min_score_pct = Column(Float, nullable=False, default=78.0)
    score_weight_rules = Column(Float, nullable=False, default=0.4)
    score_weight_market = Column(Float, nullable=False, default=0.6)

    min_volume_24h_usdt_bull = Column(Float, nullable=False, default=50000000.0)
    min_volume_24h_usdt_bear = Column(Float, nullable=False, default=70000000.0)
    min_volume_24h_usdt_range = Column(Float, nullable=False, default=90000000.0)

    max_spread_bps_bull = Column(Float, nullable=False, default=10.0)
    max_spread_bps_bear = Column(Float, nullable=False, default=8.0)
    max_spread_bps_range = Column(Float, nullable=False, default=7.0)

    max_slippage_bps_bull = Column(Float, nullable=False, default=15.0)
    max_slippage_bps_bear = Column(Float, nullable=False, default=12.0)
    max_slippage_bps_range = Column(Float, nullable=False, default=10.0)

    max_hold_minutes_bull = Column(Float, nullable=False, default=720.0)
    max_hold_minutes_bear = Column(Float, nullable=False, default=480.0)
    max_hold_minutes_range = Column(Float, nullable=False, default=360.0)

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
