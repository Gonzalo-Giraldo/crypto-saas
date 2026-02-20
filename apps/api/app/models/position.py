import uuid
from sqlalchemy import Column, String, Float, DateTime
from sqlalchemy.sql import func

from apps.api.app.db.session import Base


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    user_id = Column(String, index=True, nullable=False)
    signal_id = Column(String, index=True, nullable=False)

    symbol = Column(String, index=True, nullable=False)

    side = Column(String, nullable=False, default="LONG")  # futuro: SHORT
    qty = Column(Float, nullable=False)

    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)

    status = Column(String, index=True, nullable=False, default="OPEN")  # OPEN / CLOSED

    opened_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    realized_pnl = Column(Float, nullable=True)
    fees = Column(Float, nullable=True)
