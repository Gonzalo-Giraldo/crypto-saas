import uuid

from sqlalchemy import Column, DateTime, Float, Integer, String, UniqueConstraint, func

from apps.api.app.db.session import Base


class LearningRollupHourly(Base):
    __tablename__ = "learning_rollup_hourly"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "bucket_hour",
            "exchange",
            "symbol",
            "horizon_minutes",
            name="uq_learning_rollup_hourly_key",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True, default="default")
    partition_ym = Column(String, nullable=False, index=True)  # YYYY-MM (logical partition)

    bucket_hour = Column(DateTime(timezone=True), nullable=False, index=True)
    exchange = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=True, index=True)
    horizon_minutes = Column(Integer, nullable=False, default=60, index=True)

    samples = Column(Integer, nullable=False, default=0)
    hit_rate_pct = Column(Float, nullable=False, default=0.0)
    avg_return_pct = Column(Float, nullable=False, default=0.0)
    p50_return_pct = Column(Float, nullable=False, default=0.0)
    p90_return_pct = Column(Float, nullable=False, default=0.0)

    avg_score = Column(Float, nullable=True)
    avg_score_rules = Column(Float, nullable=True)
    avg_score_market = Column(Float, nullable=True)

    green_count = Column(Integer, nullable=False, default=0)
    gray_count = Column(Integer, nullable=False, default=0)
    red_count = Column(Integer, nullable=False, default=0)

    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
