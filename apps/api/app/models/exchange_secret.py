import uuid

from sqlalchemy import Column, DateTime, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from apps.api.app.db.session import Base


class ExchangeSecret(Base):
    __tablename__ = "exchange_secret"
    __table_args__ = (
        UniqueConstraint("user_id", "exchange", name="uq_user_exchange"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)
    exchange = Column(String, index=True, nullable=False)  # BINANCE | IBKR
    api_key_encrypted = Column(Text, nullable=False)
    api_secret_encrypted = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)
