from sqlalchemy import Column, String, Float
from apps.api.app.db.session import Base

class IbkrFill(Base):
    __tablename__ = "ibkr_fills"
    fill_id = Column(String, primary_key=True)  # trade_id
    execution_ref = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    qty = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    broker = Column(String, nullable=False, default="ibkr")
