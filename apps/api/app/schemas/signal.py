from pydantic import BaseModel
from typing import Optional


class SignalCreate(BaseModel):
    module: str
    base_risk_percent: float
    entry_price: float
    stop_loss: float
    take_profit: float


class SignalOut(BaseModel):
    id: str
    user_id: str
    symbol: str
    module: str
    base_risk_percent: Optional[float] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    status: str
    reason_codes: Optional[str] = None

    class Config:
        from_attributes = True

