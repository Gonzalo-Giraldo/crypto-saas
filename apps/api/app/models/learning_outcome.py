import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, UniqueConstraint, func

from apps.api.app.db.session import Base


class LearningDecisionOutcome(Base):
    __tablename__ = "learning_decision_outcome"
    __table_args__ = (
        UniqueConstraint("decision_id", "horizon_minutes", name="uq_learning_outcome_decision_horizon"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    decision_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=False, index=True, default="default")
    user_id = Column(String, nullable=False, index=True)
    exchange = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=True, index=True)

    partition_ym = Column(String, nullable=False, index=True)  # YYYY-MM (logical partition)
    decision_ts = Column(DateTime(timezone=True), nullable=False, index=True)
    due_at = Column(DateTime(timezone=True), nullable=False, index=True)
    horizon_minutes = Column(Integer, nullable=False, default=60)

    outcome_status = Column(String, nullable=False, default="pending", index=True)  # pending/labeled/expired/no_price
    labeled_at = Column(DateTime(timezone=True), nullable=True)

    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    price_source = Column(String, nullable=True)

    return_pct = Column(Float, nullable=True)
    pnl_quote = Column(Float, nullable=True)
    max_drawdown_pct = Column(Float, nullable=True)
    max_runup_pct = Column(Float, nullable=True)
    hit = Column(Boolean, nullable=True)
    label_rule = Column(String, nullable=True)

    meta_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
