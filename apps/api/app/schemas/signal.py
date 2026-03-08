import math
import re
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional


class SignalCreate(BaseModel):
    symbol: str
    module: str
    base_risk_percent: float
    entry_price: float
    stop_loss: float
    take_profit: float

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str):
        normalized = (value or "").strip().upper()
        if len(normalized) < 3 or len(normalized) > 30:
            raise ValueError("symbol length must be between 3 and 30")
        if not re.fullmatch(r"[A-Z0-9/_\.\-]+", normalized):
            raise ValueError("symbol has invalid format")
        return normalized

    @field_validator("module")
    @classmethod
    def validate_module(cls, value: str):
        normalized = (value or "").strip().upper()
        if len(normalized) < 2 or len(normalized) > 50:
            raise ValueError("module length must be between 2 and 50")
        if not re.fullmatch(r"[A-Z0-9_\-]+", normalized):
            raise ValueError("module has invalid format")
        return normalized

    @field_validator("base_risk_percent", "entry_price", "stop_loss", "take_profit", mode="before")
    @classmethod
    def validate_numeric_fields(cls, value):
        try:
            out = float(value)
        except Exception as exc:
            raise ValueError("numeric field must be valid") from exc
        if not math.isfinite(out):
            raise ValueError("numeric field must be finite")
        return out

    @field_validator("base_risk_percent")
    @classmethod
    def validate_base_risk_percent(cls, value: float):
        if value <= 0 or value > 100:
            raise ValueError("base_risk_percent must be within (0, 100]")
        return value

    @field_validator("entry_price", "stop_loss", "take_profit")
    @classmethod
    def validate_positive_prices(cls, value: float):
        if value <= 0:
            raise ValueError("price must be > 0")
        return value

    @model_validator(mode="after")
    def validate_long_price_structure(self):
        if not (self.stop_loss < self.entry_price < self.take_profit):
            raise ValueError("for LONG flow: stop_loss < entry_price < take_profit")
        return self


class SignalOut(BaseModel):
    id: str
    user_id: str
    symbol: str
    module: str
    base_risk_percent: Optional[float] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    status: str
    reason_codes: Optional[str] = None

    class Config:
        from_attributes = True
