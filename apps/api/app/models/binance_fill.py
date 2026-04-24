from sqlalchemy import BigInteger, Column, Integer, JSON, Numeric, String, UniqueConstraint

from apps.api.app.db.session import Base

class BinanceFill(Base):
    __tablename__ = "binance_fills"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)
    account_id = Column(String, nullable=False)
    broker = Column(String, nullable=False, default="binance")
    market = Column(String, nullable=False)
    trade_id = Column(String, nullable=False)
    order_id = Column(String, nullable=True)
    symbol = Column(String, nullable=True)
    side = Column(String, nullable=True)
    raw_payload = Column(JSON, nullable=True)
    price = Column(Numeric, nullable=True)
    qty = Column(Numeric, nullable=True)
    quote_qty = Column(Numeric, nullable=True)
    commission = Column(Numeric, nullable=True)
    commission_asset = Column(String, nullable=True)
    commission_price_usdt = Column(Numeric, nullable=True)
    commission_usdt = Column(Numeric, nullable=True)
    realized_pnl = Column(Numeric, nullable=True)
    executed_at_ms = Column(BigInteger, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "user_id", "account_id", "broker", "market", "trade_id",
            name="uq_binance_fill_identity"
        ),
    )
