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
    rr_estimate: float = 2.0
    trend_tf: str = "4H"
    signal_tf: str = "1H"
    timing_tf: str = "15M"
    spread_bps: float = 5.0
    slippage_bps: float = 10.0
    volume_24h_usdt: float = 100000000.0
    in_rth: bool = True
    macro_event_block: bool = False
    earnings_within_24h: bool = False

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: str):
        normalized = value.upper().strip()
        if normalized not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        return normalized

    @field_validator("trend_tf", "signal_tf", "timing_tf")
    @classmethod
    def normalize_tf(cls, value: str):
        return value.upper().strip()


class PretradeCheckOut(BaseModel):
    passed: bool
    exchange: str
    strategy_id: str
    strategy_source: str
    risk_profile: str
    checks: list[dict]


class ExitCheckRequest(BaseModel):
    symbol: str
    side: str
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    opened_minutes: int = 0
    trend_break: bool = False
    signal_reverse: bool = False
    macro_event_block: bool = False
    earnings_within_24h: bool = False

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: str):
        normalized = value.upper().strip()
        if normalized not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        return normalized


class ExitCheckOut(BaseModel):
    should_exit: bool
    exchange: str
    strategy_id: str
    strategy_source: str
    reasons: list[str]
    checks: list[dict]
