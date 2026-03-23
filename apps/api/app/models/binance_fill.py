from sqlalchemy import Column, Integer, String, JSON, UniqueConstraint

from apps.api.app.db.session import Base

class BinanceFill(Base):
    __tablename__ = "binance_fills"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)
    account_id = Column(String, nullable=False)
    broker = Column(String, nullable=False, default="binance")
    market = Column(String, nullable=False)  # "SPOT" or "FUTURES"
    trade_id = Column(String, nullable=False)
    order_id = Column(String, nullable=True)
    symbol = Column(String, nullable=True)
    side = Column(String, nullable=True)
    raw_payload = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "user_id", "account_id", "broker", "market", "trade_id",
            name="uq_binance_fill_identity"
        ),
    )
