from pydantic import BaseModel, field_validator
from typing import Any, Optional


ALLOWED_EXCHANGES = {"BINANCE", "IBKR"}
ALLOWED_SIDES = {"BUY", "SELL"}


class ExecutionPrepareRequest(BaseModel):
    exchange: str
    symbol: str
    side: str
    qty: float
    account_id: Optional[str] = None

    @field_validator("exchange")
    @classmethod
    def validate_exchange(cls, value: str):
        normalized = value.upper()
        if normalized not in ALLOWED_EXCHANGES:
            raise ValueError("exchange must be BINANCE or IBKR")
        return normalized

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: str):
        normalized = value.upper()
        if normalized not in ALLOWED_SIDES:
            raise ValueError("side must be BUY or SELL")
        return normalized


class ExecutionPrepareOut(BaseModel):
    mode: str
    exchange: str
    symbol: str
    side: str
    qty: float
    api_key_masked: str
    signature_preview: str

class BinanceTestOrderRequest(BaseModel):
    symbol: str
    side: str
    qty: float
    market: Optional[str] = None
    account_id: Optional[str] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: str):
        normalized = value.upper()
        if normalized not in ALLOWED_SIDES:
            raise ValueError("side must be BUY or SELL")
        return normalized

    @field_validator("market")
    @classmethod
    def validate_market(cls, value):
        if value is None:
            return value
        v = value.upper()
        if v not in ("SPOT", "FUTURES"):
            raise ValueError("market must be SPOT or FUTURES")
        return v

class BinanceTestOrderOut(BaseModel):
    exchange: str
    mode: str
    symbol: str
    side: str
    qty: float
    qty_requested: float | None = None
    client_order_id: str | None = None
    validation: dict[str, Any] | None = None
    sent: bool


class IbkrTestOrderRequest(BaseModel):
    symbol: str
    side: str
    qty: float
    account_id: Optional[str] = None

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: str):
        normalized = value.upper()
        if normalized not in ALLOWED_SIDES:
            raise ValueError("side must be BUY or SELL")
        return normalized


class IbkrTestOrderOut(BaseModel):
    exchange: str
    mode: str
    symbol: str
    side: str
    qty: float
    sent: bool
    order_ref: str


class AccountBalanceItemOut(BaseModel):
    asset: str
    free: float | None = None
    locked: float | None = None
    total: float | None = None


class PositionItemOut(BaseModel):
    symbol: str
    qty: float | None = None
    avg_price: float | None = None
    market_value: float | None = None
    unrealized_pnl: float | None = None


class AccountStatusOut(BaseModel):
    exchange: str
    mode: str
    account_id: str | None = None
    can_trade: bool | None = None
    balances: list[AccountBalanceItemOut] = []
    open_orders: int | None = None
    positions: list[PositionItemOut] = []
    metrics: dict[str, Any] = {}
