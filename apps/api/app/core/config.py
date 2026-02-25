from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ENCRYPTION_KEY: str
    BINANCE_TESTNET_BASE_URL: str = "https://testnet.binance.vision"
    DAILY_STOP: float
    MAX_TRADES: int

    model_config = ConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
