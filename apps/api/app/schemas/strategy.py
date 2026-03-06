from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator
from pydantic import Field


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
    crypto_event_block: bool = False
    leverage: float = 1.0
    funding_rate_bps: float = 0.0
    market_session: str = "AUTO"
    market_trend_score: float = 0.0
    market_trend_score_1d: Optional[float] = None
    market_trend_score_4h: Optional[float] = None
    market_trend_score_1h: Optional[float] = None
    atr_pct: float = 0.0
    momentum_score: float = 0.0

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

    @field_validator("market_session")
    @classmethod
    def normalize_market_session(cls, value: str):
        normalized = (value or "AUTO").upper().strip()
        if normalized not in {"AUTO", "RTH", "OFF_HOURS"}:
            raise ValueError("market_session must be AUTO, RTH or OFF_HOURS")
        return normalized


class PretradeCheckOut(BaseModel):
    passed: bool
    exchange: str
    strategy_id: str
    strategy_source: str
    risk_profile: str
    market_regime: str = "range"
    regime_source: str = "legacy"
    checks: list[dict]


class PretradeScanRequest(BaseModel):
    candidates: list[PretradeCheckRequest] = Field(default_factory=list)
    top_n: int = 10
    include_blocked: bool = True

    @field_validator("top_n")
    @classmethod
    def validate_top_n(cls, value: int):
        if value < 1 or value > 200:
            raise ValueError("top_n must be between 1 and 200")
        return value


class PretradeScanAssetOut(BaseModel):
    symbol: str
    side: str
    qty: float
    passed: bool
    score: float
    score_rules: Optional[float] = None
    score_market: Optional[float] = None
    market_regime: str
    regime_source: str
    passed_checks: int
    total_checks: int
    failed_checks: list[str]
    duration_ms: float
    pretrade: PretradeCheckOut


class PretradeScanOut(BaseModel):
    exchange: str
    scanned_assets: int
    returned_assets: int
    passed_assets: int
    blocked_assets: int
    duration_ms_total: float
    duration_ms_avg: float
    assets: list[PretradeScanAssetOut]


class PretradeAutoPickRequest(BaseModel):
    candidates: list[PretradeCheckRequest] = Field(default_factory=list)
    top_n: int = 10
    dry_run: bool = True

    @field_validator("top_n")
    @classmethod
    def validate_top_n(cls, value: int):
        if value < 1 or value > 200:
            raise ValueError("top_n must be between 1 and 200")
        return value


class PretradeAutoPickOut(BaseModel):
    exchange: str
    dry_run: bool
    selected: bool
    selected_symbol: Optional[str] = None
    selected_side: Optional[str] = None
    selected_qty: Optional[float] = None
    selected_score: Optional[float] = None
    selected_score_rules: Optional[float] = None
    selected_score_market: Optional[float] = None
    selected_trend_score: Optional[float] = None
    selected_trend_score_1d: Optional[float] = None
    selected_trend_score_4h: Optional[float] = None
    selected_trend_score_1h: Optional[float] = None
    selected_market_regime: Optional[str] = None
    selected_liquidity_state: Optional[str] = None
    selected_size_multiplier: Optional[float] = None
    top_candidate_symbol: Optional[str] = None
    top_candidate_score: Optional[float] = None
    top_candidate_score_rules: Optional[float] = None
    top_candidate_score_market: Optional[float] = None
    top_candidate_trend_score: Optional[float] = None
    top_candidate_trend_score_1d: Optional[float] = None
    top_candidate_trend_score_4h: Optional[float] = None
    top_candidate_trend_score_1h: Optional[float] = None
    avg_score: Optional[float] = None
    avg_score_rules: Optional[float] = None
    avg_score_market: Optional[float] = None
    decision: str
    top_failed_checks: list[str] = Field(default_factory=list)
    execution: Optional[dict] = None
    scan: PretradeScanOut


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
    market_trend_score: float = 0.0
    atr_pct: float = 0.0
    momentum_score: float = 0.0

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
    market_regime: str = "range"
    regime_source: str = "legacy"
    reasons: list[str]
    checks: list[dict]
