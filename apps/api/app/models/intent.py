from sqlalchemy import (
    Column,
    String,
    Numeric,
    DateTime,
    CheckConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
import uuid
from apps.api.app.models.base import Base

class Intent(Base):
    __tablename__ = "intents"

    intent_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    broker = Column(String, nullable=False)
    account_id = Column(String, nullable=False)
    symbol = Column(String, nullable=False, index=True)
    side = Column(String, nullable=False)
    expected_qty = Column(Numeric(24, 8), nullable=False)
    order_type = Column(String, nullable=False)
    source = Column(String, nullable=False)
    lifecycle_status = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')", name="ck_intent_side"),
        CheckConstraint("expected_qty > 0", name="ck_intent_expected_qty_positive"),
        CheckConstraint("broker IN ('BINANCE', 'IBKR')", name="ck_intent_broker"),
        CheckConstraint(
            "lifecycle_status IN ('CREATED', 'CONSUMED', 'EXECUTED', 'PARTIALLY_FILLED', 'FILLED', 'FAILED', 'CANCELLED')",
            name="ck_intent_lifecycle_status",
        ),
        Index("ix_intent_user_id_created_at", "user_id", "created_at"),
        Index("ix_intent_broker_account_id_created_at", "broker", "account_id", "created_at"),
        Index("ix_intent_lifecycle_status_created_at", "lifecycle_status", "created_at"),
        Index("ix_intent_symbol_created_at", "symbol", "created_at"),
    )
