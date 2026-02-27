from pydantic import BaseModel, field_validator


ALLOWED_EXCHANGES = {"BINANCE", "IBKR"}
ALLOWED_SIDES = {"BUY", "SELL"}


class ExecutionPrepareRequest(BaseModel):
    exchange: str
    symbol: str
    side: str
    qty: float

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

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: str):
        normalized = value.upper()
        if normalized not in ALLOWED_SIDES:
            raise ValueError("side must be BUY or SELL")
        return normalized


class BinanceTestOrderOut(BaseModel):
    exchange: str
    mode: str
    symbol: str
    side: str
    qty: float
    sent: bool


class IbkrPaperCheckRequest(BaseModel):
    symbol: str
    side: str
    qty: float

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: str):
        normalized = value.upper()
        if normalized not in ALLOWED_SIDES:
            raise ValueError("side must be BUY or SELL")
        return normalized


class IbkrPaperCheckOut(BaseModel):
    exchange: str
    mode: str
    symbol: str
    side: str
    qty: float
    credential_fingerprint: str


class IbkrTestOrderRequest(BaseModel):
    symbol: str
    side: str
    qty: float

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
