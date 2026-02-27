from __future__ import annotations

from copy import deepcopy

from apps.api.app.core.config import settings


PROFILE_MODEL2 = {
    "profile_name": "model2_conservador_productivo",
    "max_risk_per_trade_pct": 0.50,
    "max_daily_loss_pct": 1.50,
    "max_trades_per_day": 3,
    "max_open_positions": 2,
    "cooldown_between_trades_minutes": 30,
    "max_leverage": 1.0,
    "stop_loss_required": True,
    "min_rr": 1.5,
}

PROFILE_LOOSE = {
    "profile_name": "modelo_suelto_controlado",
    "max_risk_per_trade_pct": 0.75,
    "max_daily_loss_pct": 2.00,
    "max_trades_per_day": 4,
    "max_open_positions": 2,
    "cooldown_between_trades_minutes": 20,
    "max_leverage": 1.0,
    "stop_loss_required": True,
    "min_rr": 1.3,
}


def _norm_email(value: str | None) -> str:
    return (value or "").strip().lower()


def resolve_risk_profile_for_email(email: str) -> dict:
    model2_email = _norm_email(settings.RISK_PROFILE_MODEL2_EMAIL)
    loose_email = _norm_email(settings.RISK_PROFILE_LOOSE_EMAIL)
    target = _norm_email(email)

    if target and target == loose_email:
        return deepcopy(PROFILE_LOOSE)
    if target and target == model2_email:
        return deepcopy(PROFILE_MODEL2)
    return deepcopy(PROFILE_MODEL2)


def apply_profile_daily_limits(dr, profile: dict):
    # Current engine stores daily stop as a negative threshold.
    dr.daily_stop = -abs(float(profile["max_daily_loss_pct"]))
    dr.max_trades = int(profile["max_trades_per_day"])
