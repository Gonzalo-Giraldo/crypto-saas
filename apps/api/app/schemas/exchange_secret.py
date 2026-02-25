from datetime import datetime
from pydantic import BaseModel, field_validator


ALLOWED_EXCHANGES = {"BINANCE", "IBKR"}


class ExchangeSecretUpsert(BaseModel):
    exchange: str
    api_key: str
    api_secret: str

    @field_validator("exchange")
    @classmethod
    def validate_exchange(cls, value: str):
        normalized = value.upper()
        if normalized not in ALLOWED_EXCHANGES:
            raise ValueError("exchange must be BINANCE or IBKR")
        return normalized


class ExchangeSecretOut(BaseModel):
    exchange: str
    configured: bool
    updated_at: datetime

    class Config:
        from_attributes = True
