from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ENCRYPTION_KEY: str
    BINANCE_TESTNET_BASE_URL: str = "https://testnet.binance.vision"
    IBKR_BRIDGE_BASE_URL: str = ""
    RISK_PROFILE_MODEL2_EMAIL: str = ""
    RISK_PROFILE_LOOSE_EMAIL: str = ""
    DAILY_STOP: float
    MAX_TRADES: int
    ENFORCE_2FA_FOR_ADMINS: bool = False
    ENFORCE_2FA_EMAILS: str = ""

    model_config = ConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
