from pydantic import BaseModel


class ReencryptSecretsRequest(BaseModel):
    old_key: str
    new_key: str
    dry_run: bool = True


class ReencryptSecretsOut(BaseModel):
    dry_run: bool
    scanned: int
    updated: int


class SecurityPostureUserOut(BaseModel):
    user_id: str
    email: str
    role: str
    two_factor_enabled: bool
    binance_secret_configured: bool
    ibkr_secret_configured: bool
    oldest_secret_age_days: int | None
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
    trends_7d: list[DashboardTrendDayOut]
    users: list[DashboardUserOut]
