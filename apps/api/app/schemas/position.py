from pydantic import BaseModel
from typing import Optional


class PositionOut(BaseModel):
    id: str
    user_id: str
    signal_id: str
    symbol: str
    side: str
    qty: float
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    status: str
    realized_pnl: Optional[float] = None
    fees: Optional[float] = None

    class Config:
        from_attributes = True
