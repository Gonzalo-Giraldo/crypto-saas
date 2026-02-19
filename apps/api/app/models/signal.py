import uuid
from sqlalchemy import Column, String, Float, DateTime, Text
from sqlalchemy.sql import func

from apps.api.app.db.session import Base


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # dueño de la señal
    user_id = Column(String, index=True, nullable=False)

    # mercado / estrategia
    symbol = Column(String, index=True, nullable=False)      # e.g. "BTC/USDT"
    module = Column(String, nullable=False)                  # e.g. "DAY_TREND"

    # parámetros de riesgo de la señal
    base_risk_percent = Column(Float, nullable=True)         # opcional

    # precios propuestos (pueden ser None si después se calculan)
    entry_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)

    # estado
    status = Column(String, index=True, nullable=False, default="CREATED")
    reason_codes = Column(Text, nullable=True)               # por qué se aceptó/rechazó (csv/json simple)

    # timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)

