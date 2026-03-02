from typing import Optional

from pydantic import BaseModel


class ReencryptSecretsRequest(BaseModel):
    old_key: str
    new_key: str
    dry_run: bool = True


class ReencryptSecretsOut(BaseModel):
    dry_run: bool
    scanned: int
    updated: int


class CleanupSmokeUsersUserOut(BaseModel):
    user_id: str
    email: str
    last_activity_at: Optional[str]
    eligible_for_delete: bool


class CleanupSmokeUsersOut(BaseModel):
    dry_run: bool
    older_than_days: int
    scanned: int
    eligible: int
    deleted: int
    users: list[CleanupSmokeUsersUserOut]


class SecurityPostureUserOut(BaseModel):
    user_id: str
    email: str
    role: str
    two_factor_enabled: bool
    binance_secret_configured: bool
    ibkr_secret_configured: bool
    oldest_secret_age_days: Optional[int]
    stale_secret: bool


class SecurityPostureSummaryOut(BaseModel):
    total_users: int
    users_missing_2fa: int
    users_with_stale_secrets: int


class SecurityPostureOut(BaseModel):
    generated_at: str
    max_secret_age_days: int
    real_only: bool
    summary: SecurityPostureSummaryOut
    users: list[SecurityPostureUserOut]


class DashboardUserOut(BaseModel):
    user_id: str
    email: str
    role: str
    risk_profile: str
    two_factor_enabled: bool
    binance_secret_configured: bool
    ibkr_secret_configured: bool
    trades_today: int
    open_positions_now: int
    blocked_open_attempts_today: int
    realized_pnl_today: float


class DashboardSecurityOut(BaseModel):
    total_users: int
    users_missing_2fa: int
    users_with_stale_secrets: int
    max_secret_age_days: int


class DashboardOperationsOut(BaseModel):
    trades_today_total: int
    open_positions_total: int
    blocked_open_attempts_total: int


class DashboardEventsOut(BaseModel):
    errors_last_24h: int
    pretrade_blocked_last_24h: int


class DashboardProfileProductivityOut(BaseModel):
    risk_profile: str
    users_count: int
    trades_today_total: int
    blocked_open_attempts_total: int
    realized_pnl_today_total: float
    avg_realized_pnl_per_user: float
    trades_utilization_pct: float


class DashboardTrendDayOut(BaseModel):
    day: str
    trades_total: int
    blocked_open_attempts_total: int
    errors_total: int


class DashboardSummaryOut(BaseModel):
    generated_at: str
    day: str
    overall_status: str
    generated_for: str
    security: DashboardSecurityOut
    operations: DashboardOperationsOut
    recent_events: DashboardEventsOut
    profile_productivity: list[DashboardProfileProductivityOut]
    trends_7d: list[DashboardTrendDayOut]
    users: list[DashboardUserOut]


class TradingControlUpdateRequest(BaseModel):
    trading_enabled: bool
    reason: Optional[str] = None


class TradingControlOut(BaseModel):
    trading_enabled: bool
    updated_by: Optional[str] = None
    reason: Optional[str] = None


class IdempotencyStatsOut(BaseModel):
    records_total: int
    max_age_days: int
    oldest_record_at: Optional[str] = None
    newest_record_at: Optional[str] = None


class IdempotencyCleanupOut(BaseModel):
    deleted: int
    max_age_days: int


class BackofficeSummaryOut(BaseModel):
    tenant_id: str
    total_users: int
    admins: int
    operators: int
    viewers: int
    traders: int
    disabled: int
    users_missing_2fa: int
    users_with_stale_secrets: int


class BackofficeUserOut(BaseModel):
    user_id: str
    email: str
    role: str
    two_factor_enabled: bool
    binance_enabled: bool
    ibkr_enabled: bool
    binance_secret_configured: bool
    ibkr_secret_configured: bool
    readiness: str


class RiskProfileConfigOut(BaseModel):
    profile_name: str
    max_risk_per_trade_pct: float
    max_daily_loss_pct: float
    max_trades_per_day: int
    max_open_positions: int
    cooldown_between_trades_minutes: float
    max_leverage: float
    stop_loss_required: bool
    min_rr: float


class RiskProfileConfigUpdateRequest(BaseModel):
    max_risk_per_trade_pct: float
    max_daily_loss_pct: float
    max_trades_per_day: int
    max_open_positions: int
    cooldown_between_trades_minutes: float
    max_leverage: float = 1.0
    stop_loss_required: bool = True
    min_rr: float


class StrategyRuntimePolicyOut(BaseModel):
    strategy_id: str
    exchange: str
    allow_bull: bool
    allow_bear: bool
    allow_range: bool
    rr_min_bull: float
    rr_min_bear: float
    rr_min_range: float
    min_volume_24h_usdt_bull: float
    min_volume_24h_usdt_bear: float
    min_volume_24h_usdt_range: float
    max_spread_bps_bull: float
    max_spread_bps_bear: float
    max_spread_bps_range: float
    max_slippage_bps_bull: float
    max_slippage_bps_bear: float
    max_slippage_bps_range: float
    max_hold_minutes_bull: float
    max_hold_minutes_bear: float
    max_hold_minutes_range: float
    updated_at: Optional[str] = None


class StrategyRuntimePolicyUpdateRequest(BaseModel):
    allow_bull: bool
    allow_bear: bool
    allow_range: bool
    rr_min_bull: float
    rr_min_bear: float
    rr_min_range: float
    min_volume_24h_usdt_bull: float = 0.0
    min_volume_24h_usdt_bear: float = 0.0
    min_volume_24h_usdt_range: float = 0.0
    max_spread_bps_bull: float
    max_spread_bps_bear: float
    max_spread_bps_range: float
    max_slippage_bps_bull: float
    max_slippage_bps_bear: float
    max_slippage_bps_range: float
    max_hold_minutes_bull: float
    max_hold_minutes_bear: float
    max_hold_minutes_range: float


class AutoPickReportItemOut(BaseModel):
    timestamp: str
    bucket_5m: str
    user_email: str
    exchange: str
    dry_run: bool
    selected: bool
    bought: bool
    symbol: Optional[str] = None
    side: Optional[str] = None
    qty: Optional[float] = None
    score: Optional[float] = None
    market_regime: Optional[str] = None
    decision: str
    reason: str
    scanned_assets: int = 0


class AutoPickReportOut(BaseModel):
    generated_at: str
    hours: int
    window_from: str
    window_to: str
    interval_minutes: int
    rows: list[AutoPickReportItemOut]
