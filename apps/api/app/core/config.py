from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ENCRYPTION_KEY: str
    BINANCE_TESTNET_BASE_URL: str = "https://testnet.binance.vision"
    BINANCE_GATEWAY_ENABLED: bool = False
    BINANCE_GATEWAY_BASE_URL: str = ""
    BINANCE_GATEWAY_TOKEN: str = ""
    BINANCE_GATEWAY_TIMEOUT_SECONDS: int = 12
    BINANCE_GATEWAY_FALLBACK_DIRECT: bool = True
    IBKR_BRIDGE_BASE_URL: str = ""
    RISK_PROFILE_MODEL2_EMAIL: str = ""
    RISK_PROFILE_LOOSE_EMAIL: str = ""
    DAILY_STOP: float
    MAX_TRADES: int
    ENFORCE_2FA_FOR_ADMINS: bool = False
    ENFORCE_2FA_EMAILS: str = ""
    PASSWORD_MAX_AGE_DAYS: int = 0
    ENFORCE_PASSWORD_MAX_AGE: bool = False
    TRADING_ENABLED_DEFAULT: bool = True
    MAX_OPEN_QTY_PER_SYMBOL: float = 0.0
    MAX_OPEN_NOTIONAL_PER_EXCHANGE: float = 0.0
    DEFAULT_CAPITAL_BASE_USD: float = 10000.0
    ALLOWED_BINANCE_SYMBOLS: str = ""
    ALLOWED_IBKR_SYMBOLS: str = ""
    IDEMPOTENCY_KEY_MAX_AGE_DAYS: int = 30
    AUDIT_EXPORT_SIGNING_KEY: str = ""

    model_config = ConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
