import uuid

from sqlalchemy import Boolean, Column, DateTime, String, UniqueConstraint
from sqlalchemy.sql import func

from apps.api.app.db.session import Base


class StrategyAssignment(Base):
    __tablename__ = "strategy_assignment"
    __table_args__ = (
        UniqueConstraint("user_id", "exchange", name="uq_strategy_user_exchange"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)
    exchange = Column(String, index=True, nullable=False)  # BINANCE | IBKR
    strategy_id = Column(String, nullable=False, default="SWING_V1")
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)
