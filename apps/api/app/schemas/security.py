from typing import Optional

from pydantic import BaseModel


class ReencryptSecretsRequest(BaseModel):
    old_key: str
    new_key: str
    dry_run: bool = True
    new_version: str = "v2"
    batch_size: int = 200
    canary_count: Optional[int] = None


class ReencryptSecretsOut(BaseModel):
    dry_run: bool
    scanned: int
    updated: int
    failed: int = 0
    batch_size: int = 200
    batches: int = 0
    new_version: Optional[str] = None
    canary_count: Optional[int] = None


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
    min_score_pct: float = 78.0
    score_weight_rules: float = 0.4
    score_weight_market: float = 0.6
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
    min_score_pct: float = 78.0
    score_weight_rules: float = 0.4
    score_weight_market: float = 0.6
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
    score_rules: Optional[float] = None
    score_market: Optional[float] = None
    trend_score: Optional[float] = None
    trend_score_1d: Optional[float] = None
    trend_score_4h: Optional[float] = None
    trend_score_1h: Optional[float] = None
    micro_trend_15m: Optional[float] = None
    top_candidate_trend_score: Optional[float] = None
    top_candidate_trend_score_1d: Optional[float] = None
    top_candidate_trend_score_4h: Optional[float] = None
    top_candidate_trend_score_1h: Optional[float] = None
    top_candidate_micro_trend_15m: Optional[float] = None
    avg_score: Optional[float] = None
    avg_score_rules: Optional[float] = None
    avg_score_market: Optional[float] = None
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


class AutoPickLiquidityEventOut(BaseModel):
    timestamp: str
    user_email: str
    exchange: str
    decision: str
    selected_symbol: Optional[str] = None
    selected_score: Optional[float] = None
    selected_qty: Optional[float] = None
    liquidity_state: Optional[str] = None
    size_multiplier: Optional[float] = None
    scanned_assets: int = 0


class AutoPickLiquidityReportOut(BaseModel):
    generated_at: str
    hours: int
    window_from: str
    window_to: str
    total_events: int
    green_events: int
    gray_events: int
    red_events: int
    blocked_events: int
    blocked_rate_pct: float
    rows: list[AutoPickLiquidityEventOut]


class MarketTrendSnapshotOut(BaseModel):
    timestamp: str
    bucket_5m: str
    exchange: str
    symbol: str
    regime: str
    confidence: float
    trend_score: float
    momentum_score: float
    atr_pct: float
    volume_24h_usdt: float
    source: str


class MarketTrendMonitorOut(BaseModel):
    generated_at: str
    hours: int
    window_from: str
    window_to: str
    exchange: str
    total_rows: int
    rows: list[MarketTrendSnapshotOut]


class LearningLabelRunOut(BaseModel):
    dry_run: bool
    horizon_minutes: int
    scanned: int
    labeled: int
    expired: int
    no_price: int
    labeled_rate_pct: float = 0.0
    expired_rate_pct: float = 0.0
    no_price_rate_pct: float = 0.0


class LearningRetentionRunOut(BaseModel):
    dry_run: bool
    raw_ttl_days: int
    rollup_ttl_days: int
    deleted_snapshots: int
    deleted_outcomes: int
    deleted_rollups: int


class LearningDatasetRowOut(BaseModel):
    decision_id: str
    timestamp: str
    due_at: Optional[str] = None
    tenant_id: str
    user_id: str
    exchange: str
    symbol: Optional[str] = None
    decision: str
    selected: bool
    dry_run: bool
    selected_score: Optional[float] = None
    selected_score_rules: Optional[float] = None
    selected_score_market: Optional[float] = None
    selected_liquidity_state: Optional[str] = None
    rr_estimate: Optional[float] = None
    trend_score: Optional[float] = None
    momentum_score: Optional[float] = None
    atr_pct: Optional[float] = None
    volume_24h_usdt: Optional[float] = None
    horizon_minutes: int
    outcome_status: Optional[str] = None
    return_pct: Optional[float] = None
    pnl_quote: Optional[float] = None
    hit: Optional[bool] = None


class LearningDatasetOut(BaseModel):
    generated_at: str
    hours: int
    window_from: str
    window_to: str
    rows: list[LearningDatasetRowOut]


class LearningRollupRowOut(BaseModel):
    bucket_hour: str
    exchange: str
    symbol: Optional[str] = None
    horizon_minutes: int
    samples: int
    hit_rate_pct: float
    avg_return_pct: float
    p50_return_pct: float
    p90_return_pct: float
    avg_score: Optional[float] = None
    avg_score_rules: Optional[float] = None
    avg_score_market: Optional[float] = None
    green_count: int
    gray_count: int
    red_count: int


class LearningRollupOut(BaseModel):
    generated_at: str
    hours: int
    window_from: str
    window_to: str
    rows: list[LearningRollupRowOut]


class LearningStatusOut(BaseModel):
    generated_at: str
    pending: int
    labeled: int
    expired: int
    no_price: int
    snapshots_total: int
    outcomes_total: int
    pending_rate_pct: float = 0.0
    labeled_rate_pct: float = 0.0
    expired_rate_pct: float = 0.0
    no_price_rate_pct: float = 0.0


class LearningSuggestionReportRowOut(BaseModel):
    decision_id: str
    timestamp: str
    user_email: str
    exchange: str
    symbol: Optional[str] = None
    side: Optional[str] = None
    selected: bool
    decision: str
    score_base: Optional[float] = None
    score_final: Optional[float] = None
    learning_prob_hit_pct: Optional[float] = None
    learning_samples: Optional[int] = None
    learning_score: Optional[float] = None
    learning_delta_points: Optional[float] = None
    outcome_status: Optional[str] = None
    hit: Optional[bool] = None
    return_pct: Optional[float] = None
    pnl_quote: Optional[float] = None
    suggestion_success: Optional[bool] = None


class LearningSuggestionReportOut(BaseModel):
    generated_at: str
    hours: int
    window_from: str
    window_to: str
    total_rows: int
    success_rate_pct: Optional[float] = None
    rows: list[LearningSuggestionReportRowOut]


class AutoExitTickItemOut(BaseModel):
    user_email: str
    exchange: str
    position_id: str
    symbol: str
    side: str
    opened_minutes: int
    should_exit: bool
    closed: bool
    reason: str
    dry_run: bool
    entry_price: float
    current_price: Optional[float] = None
    realized_pnl: Optional[float] = None


class AutoExitTickOut(BaseModel):
    dry_run: bool
    paused: bool = False
    scanned_positions: int
    exit_candidates: int
    closed_positions: int
    skipped_no_price: int
    skipped_by_policy: int = 0
    errors: int = 0
    results: list[AutoExitTickItemOut]


class CIWorkflowStatusOut(BaseModel):
    key: str
    label: str
    workflow_file: str
    run_id: Optional[int] = None
    run_number: Optional[int] = None
    status: str = "unknown"
    conclusion: Optional[str] = None
    state: str = "yellow"  # green|yellow|red
    html_url: Optional[str] = None
    updated_at: Optional[str] = None
    event: Optional[str] = None
    branch: Optional[str] = None
    note: Optional[str] = None


class CIStatusOut(BaseModel):
    generated_at: str
    owner: str
    repo: str
    branch: str
    workflows: list[CIWorkflowStatusOut]


class CILogHintOut(BaseModel):
    generated_at: str
    line_for_registro_operacion_diaria: str
    runs: dict
