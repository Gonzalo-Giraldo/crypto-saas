from __future__ import annotations

from copy import deepcopy

from apps.api.app.core.config import settings
from apps.api.app.models.risk_profile_config import RiskProfileConfig
from apps.api.app.models.user_risk_profile import UserRiskProfileOverride


DEFAULT_PROFILE_MODEL2 = {
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

DEFAULT_PROFILE_LOOSE = {
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

DEFAULT_PROFILES = {
    DEFAULT_PROFILE_MODEL2["profile_name"]: DEFAULT_PROFILE_MODEL2,
    DEFAULT_PROFILE_LOOSE["profile_name"]: DEFAULT_PROFILE_LOOSE,
}


def _norm_email(value: str | None) -> str:
    return (value or "").strip().lower()


def _row_to_profile(row: RiskProfileConfig) -> dict:
    return {
        "profile_name": row.profile_name,
        "max_risk_per_trade_pct": float(row.max_risk_per_trade_pct),
        "max_daily_loss_pct": float(row.max_daily_loss_pct),
        "max_trades_per_day": int(row.max_trades_per_day),
        "max_open_positions": int(row.max_open_positions),
        "cooldown_between_trades_minutes": float(row.cooldown_between_trades_minutes),
        "max_leverage": float(row.max_leverage),
        "stop_loss_required": bool(row.stop_loss_required),
        "min_rr": float(row.min_rr),
    }


def get_profiles_map(db) -> dict[str, dict]:
    profiles = {k: deepcopy(v) for k, v in DEFAULT_PROFILES.items()}
    rows = db.query(RiskProfileConfig).all()
    for row in rows:
        profiles[row.profile_name] = _row_to_profile(row)
    return profiles


def list_risk_profiles(db) -> list[dict]:
    profiles = get_profiles_map(db)
    return [deepcopy(profiles[k]) for k in sorted(profiles.keys())]


def resolve_risk_profile_for_email(db, email: str) -> dict:
    profiles = get_profiles_map(db)
    model2_email = _norm_email(settings.RISK_PROFILE_MODEL2_EMAIL)
    loose_email = _norm_email(settings.RISK_PROFILE_LOOSE_EMAIL)
    target = _norm_email(email)

    if target and target == loose_email and "modelo_suelto_controlado" in profiles:
        return deepcopy(profiles["modelo_suelto_controlado"])
    if target and target == model2_email and "model2_conservador_productivo" in profiles:
        return deepcopy(profiles["model2_conservador_productivo"])
    # default fallback
    if "model2_conservador_productivo" in profiles:
        return deepcopy(profiles["model2_conservador_productivo"])
    first_key = sorted(profiles.keys())[0]
    return deepcopy(profiles[first_key])


def resolve_risk_profile(
    db,
    user_id: str,
    email: str,
) -> dict:
    profiles = get_profiles_map(db)
    override = (
        db.query(UserRiskProfileOverride)
        .filter(UserRiskProfileOverride.user_id == user_id)
        .first()
    )
    if override and override.profile_name in profiles:
        return deepcopy(profiles[override.profile_name])
    return resolve_risk_profile_for_email(db, email)


def list_profile_names(db=None) -> list[str]:
    if db is None:
        return sorted(DEFAULT_PROFILES.keys())
    return sorted(get_profiles_map(db).keys())


def upsert_risk_profile_config(
    db,
    *,
    profile_name: str,
    max_risk_per_trade_pct: float,
    max_daily_loss_pct: float,
    max_trades_per_day: int,
    max_open_positions: int,
    cooldown_between_trades_minutes: float,
    max_leverage: float,
    stop_loss_required: bool,
    min_rr: float,
) -> dict:
    row = (
        db.query(RiskProfileConfig)
        .filter(RiskProfileConfig.profile_name == profile_name)
        .first()
    )
    if not row:
        row = RiskProfileConfig(profile_name=profile_name)
        db.add(row)
    row.max_risk_per_trade_pct = float(max_risk_per_trade_pct)
    row.max_daily_loss_pct = float(max_daily_loss_pct)
    row.max_trades_per_day = int(max_trades_per_day)
    row.max_open_positions = int(max_open_positions)
    row.cooldown_between_trades_minutes = float(cooldown_between_trades_minutes)
    row.max_leverage = float(max_leverage)
    row.stop_loss_required = bool(stop_loss_required)
    row.min_rr = float(min_rr)
    db.flush()
    return _row_to_profile(row)


def apply_profile_daily_limits(dr, profile: dict):
    # Current engine stores daily stop as a negative threshold.
    dr.daily_stop = -abs(float(profile["max_daily_loss_pct"]))
    dr.max_trades = int(profile["max_trades_per_day"])
