import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, UniqueConstraint, func

from apps.api.app.db.session import Base


class LearningDecisionSnapshot(Base):
    __tablename__ = "learning_decision_snapshot"
    __table_args__ = (
        UniqueConstraint("decision_id", name="uq_learning_decision_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    decision_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=False, index=True, default="default")
    user_id = Column(String, nullable=False, index=True)
    user_email = Column(String, nullable=False, index=True)
    exchange = Column(String, nullable=False, index=True)

    partition_ym = Column(String, nullable=False, index=True)  # YYYY-MM (logical partition)
    decision_ts = Column(DateTime(timezone=True), nullable=False, index=True)
    target_horizon_minutes = Column(Integer, nullable=False, default=60)

    dry_run = Column(Boolean, nullable=False, default=True)
    selected = Column(Boolean, nullable=False, default=False)
    decision = Column(String, nullable=False, index=True)

    selected_symbol = Column(String, nullable=True, index=True)
    selected_side = Column(String, nullable=True)
    selected_qty = Column(Float, nullable=True)
    selected_score = Column(Float, nullable=True)
    selected_score_rules = Column(Float, nullable=True)
    selected_score_market = Column(Float, nullable=True)
    selected_market_regime = Column(String, nullable=True)
    selected_liquidity_state = Column(String, nullable=True)
    selected_size_multiplier = Column(Float, nullable=True)

    top_candidate_symbol = Column(String, nullable=True)
    top_candidate_score = Column(Float, nullable=True)
    top_candidate_score_rules = Column(Float, nullable=True)
    top_candidate_score_market = Column(Float, nullable=True)
    avg_score = Column(Float, nullable=True)
    avg_score_rules = Column(Float, nullable=True)
    avg_score_market = Column(Float, nullable=True)
    scanned_assets = Column(Integer, nullable=False, default=0)

    min_score_pct = Column(Float, nullable=False, default=78.0)
    score_weight_rules = Column(Float, nullable=False, default=0.4)
    score_weight_market = Column(Float, nullable=False, default=0.6)

    spread_bps = Column(Float, nullable=True)
    slippage_bps = Column(Float, nullable=True)
    max_spread_bps = Column(Float, nullable=True)
    max_slippage_bps = Column(Float, nullable=True)

    rr_estimate = Column(Float, nullable=True)
    trend_score = Column(Float, nullable=True)
    momentum_score = Column(Float, nullable=True)
    atr_pct = Column(Float, nullable=True)
    volume_24h_usdt = Column(Float, nullable=True)

    entry_price = Column(Float, nullable=True)
    entry_price_source = Column(String, nullable=True)

    top_failed_checks_json = Column(Text, nullable=True)
    checks_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
