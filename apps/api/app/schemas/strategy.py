from pydantic import BaseModel, EmailStr, field_validator


class StrategyAssignRequest(BaseModel):
    user_email: EmailStr
    exchange: str
    strategy_id: str
    enabled: bool = True

    @field_validator("exchange")
    @classmethod
    def validate_exchange(cls, value: str):
        normalized = value.upper().strip()
        if normalized not in {"BINANCE", "IBKR"}:
            raise ValueError("exchange must be BINANCE or IBKR")
        return normalized

    @field_validator("strategy_id")
    @classmethod
    def validate_strategy(cls, value: str):
        normalized = value.upper().strip()
        if normalized not in {"SWING_V1", "INTRADAY_V1"}:
            raise ValueError("strategy_id must be SWING_V1 or INTRADAY_V1")
        return normalized


class StrategyAssignOut(BaseModel):
    user_id: str
    user_email: str
    exchange: str
    strategy_id: str
    enabled: bool


class StrategyAssignmentOut(BaseModel):
    user_id: str
    user_email: str
    exchange: str
    strategy_id: str
    enabled: bool


class PretradeCheckRequest(BaseModel):
    symbol: str
    side: str
    qty: float

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: str):
        normalized = value.upper().strip()
        if normalized not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        return normalized


class PretradeCheckOut(BaseModel):
    passed: bool
    exchange: str
    strategy_id: str
    strategy_source: str
    risk_profile: str
    checks: list[dict]
