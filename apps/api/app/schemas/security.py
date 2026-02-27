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
