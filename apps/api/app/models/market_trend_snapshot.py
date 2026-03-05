import uuid

from sqlalchemy import Column, DateTime, Float, String, func

from apps.api.app.db.session import Base


class MarketTrendSnapshot(Base):
    __tablename__ = "market_trend_snapshot"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False, index=True, default="default")
    exchange = Column(String, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    regime = Column(String, nullable=False, index=True, default="range")
    confidence = Column(Float, nullable=False, default=0.0)
    trend_score = Column(Float, nullable=False, default=0.0)
    momentum_score = Column(Float, nullable=False, default=0.0)
    atr_pct = Column(Float, nullable=False, default=0.0)
    volume_24h_usdt = Column(Float, nullable=False, default=0.0)
    source = Column(String, nullable=False, default="fallback")
    bucket_5m = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
