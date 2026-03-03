from __future__ import annotations

from copy import deepcopy

from apps.api.app.models.strategy_runtime_policy import StrategyRuntimePolicy


DEFAULT_RUNTIME_POLICIES = {
    ("SWING_V1", "BINANCE"): {
        "strategy_id": "SWING_V1",
        "exchange": "BINANCE",
        "allow_bull": True,
        "allow_bear": True,
        "allow_range": False,
        "rr_min_bull": 1.5,
        "rr_min_bear": 1.6,
        "rr_min_range": 1.9,
        "min_score_pct": 78.0,
        "min_volume_24h_usdt_bull": 50000000.0,
        "min_volume_24h_usdt_bear": 70000000.0,
        "min_volume_24h_usdt_range": 90000000.0,
        "max_spread_bps_bull": 10.0,
        "max_spread_bps_bear": 8.0,
        "max_spread_bps_range": 7.0,
        "max_slippage_bps_bull": 15.0,
        "max_slippage_bps_bear": 12.0,
        "max_slippage_bps_range": 10.0,
        "max_hold_minutes_bull": 720.0,
        "max_hold_minutes_bear": 480.0,
        "max_hold_minutes_range": 360.0,
    },
    ("SWING_V1", "IBKR"): {
        "strategy_id": "SWING_V1",
        "exchange": "IBKR",
        "allow_bull": True,
        "allow_bear": True,
        "allow_range": False,
        "rr_min_bull": 1.4,
        "rr_min_bear": 1.5,
        "rr_min_range": 1.8,
        "min_score_pct": 78.0,
        "min_volume_24h_usdt_bull": 0.0,
        "min_volume_24h_usdt_bear": 0.0,
        "min_volume_24h_usdt_range": 0.0,
        "max_spread_bps_bull": 12.0,
        "max_spread_bps_bear": 10.0,
        "max_spread_bps_range": 8.0,
        "max_slippage_bps_bull": 15.0,
        "max_slippage_bps_bear": 12.0,
        "max_slippage_bps_range": 10.0,
        "max_hold_minutes_bull": 720.0,
        "max_hold_minutes_bear": 480.0,
        "max_hold_minutes_range": 360.0,
    },
    ("INTRADAY_V1", "BINANCE"): {
        "strategy_id": "INTRADAY_V1",
        "exchange": "BINANCE",
        "allow_bull": True,
        "allow_bear": True,
        "allow_range": False,
        "rr_min_bull": 1.3,
        "rr_min_bear": 1.4,
        "rr_min_range": 1.6,
        "min_score_pct": 78.0,
        "min_volume_24h_usdt_bull": 80000000.0,
        "min_volume_24h_usdt_bear": 100000000.0,
        "min_volume_24h_usdt_range": 120000000.0,
        "max_spread_bps_bull": 8.0,
        "max_spread_bps_bear": 7.0,
        "max_spread_bps_range": 6.0,
        "max_slippage_bps_bull": 12.0,
        "max_slippage_bps_bear": 10.0,
        "max_slippage_bps_range": 8.0,
        "max_hold_minutes_bull": 240.0,
        "max_hold_minutes_bear": 180.0,
        "max_hold_minutes_range": 120.0,
    },
    ("INTRADAY_V1", "IBKR"): {
        "strategy_id": "INTRADAY_V1",
        "exchange": "IBKR",
        "allow_bull": True,
        "allow_bear": True,
        "allow_range": False,
        "rr_min_bull": 1.3,
        "rr_min_bear": 1.4,
        "rr_min_range": 1.6,
        "min_score_pct": 78.0,
        "min_volume_24h_usdt_bull": 0.0,
        "min_volume_24h_usdt_bear": 0.0,
        "min_volume_24h_usdt_range": 0.0,
        "max_spread_bps_bull": 10.0,
        "max_spread_bps_bear": 8.0,
        "max_spread_bps_range": 6.0,
        "max_slippage_bps_bull": 12.0,
        "max_slippage_bps_bear": 10.0,
        "max_slippage_bps_range": 8.0,
        "max_hold_minutes_bull": 240.0,
        "max_hold_minutes_bear": 180.0,
        "max_hold_minutes_range": 120.0,
    },
}


def _normalize(strategy_id: str, exchange: str) -> tuple[str, str]:
    strategy = (strategy_id or "").upper().strip()
    ex = (exchange or "").upper().strip()
    if strategy not in {"SWING_V1", "INTRADAY_V1"}:
        raise ValueError("strategy_id must be SWING_V1 or INTRADAY_V1")
    if ex not in {"BINANCE", "IBKR"}:
        raise ValueError("exchange must be BINANCE or IBKR")
    return strategy, ex


def _to_dict(row: StrategyRuntimePolicy) -> dict:
    return {
        "strategy_id": row.strategy_id,
        "exchange": row.exchange,
        "allow_bull": bool(row.allow_bull),
        "allow_bear": bool(row.allow_bear),
        "allow_range": bool(row.allow_range),
        "rr_min_bull": float(row.rr_min_bull),
        "rr_min_bear": float(row.rr_min_bear),
        "rr_min_range": float(row.rr_min_range),
        "min_score_pct": float(row.min_score_pct),
        "min_volume_24h_usdt_bull": float(row.min_volume_24h_usdt_bull),
        "min_volume_24h_usdt_bear": float(row.min_volume_24h_usdt_bear),
        "min_volume_24h_usdt_range": float(row.min_volume_24h_usdt_range),
        "max_spread_bps_bull": float(row.max_spread_bps_bull),
        "max_spread_bps_bear": float(row.max_spread_bps_bear),
        "max_spread_bps_range": float(row.max_spread_bps_range),
        "max_slippage_bps_bull": float(row.max_slippage_bps_bull),
        "max_slippage_bps_bear": float(row.max_slippage_bps_bear),
        "max_slippage_bps_range": float(row.max_slippage_bps_range),
        "max_hold_minutes_bull": float(row.max_hold_minutes_bull),
        "max_hold_minutes_bear": float(row.max_hold_minutes_bear),
        "max_hold_minutes_range": float(row.max_hold_minutes_range),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def resolve_runtime_policy(db, strategy_id: str, exchange: str) -> dict:
    strategy, ex = _normalize(strategy_id, exchange)
    out = deepcopy(DEFAULT_RUNTIME_POLICIES[(strategy, ex)])
    row = (
        db.query(StrategyRuntimePolicy)
        .filter(
            StrategyRuntimePolicy.strategy_id == strategy,
            StrategyRuntimePolicy.exchange == ex,
        )
        .first()
    )
    if row:
        out.update(_to_dict(row))
    return out


def list_runtime_policies(db) -> list[dict]:
    rows = db.query(StrategyRuntimePolicy).all()
    row_map = {(r.strategy_id, r.exchange): r for r in rows}
    out: list[dict] = []
    for key in sorted(DEFAULT_RUNTIME_POLICIES.keys()):
        strategy, exchange = key
        if key in row_map:
            out.append(_to_dict(row_map[key]))
        else:
            base = deepcopy(DEFAULT_RUNTIME_POLICIES[key])
            base["updated_at"] = None
            out.append(base)
    return out


def upsert_runtime_policy(db, *, strategy_id: str, exchange: str, payload: dict) -> dict:
    strategy, ex = _normalize(strategy_id, exchange)
    row = (
        db.query(StrategyRuntimePolicy)
        .filter(
            StrategyRuntimePolicy.strategy_id == strategy,
            StrategyRuntimePolicy.exchange == ex,
        )
        .first()
    )
    if not row:
        row = StrategyRuntimePolicy(strategy_id=strategy, exchange=ex)
        db.add(row)

    row.allow_bull = bool(payload["allow_bull"])
    row.allow_bear = bool(payload["allow_bear"])
    row.allow_range = bool(payload["allow_range"])
    row.rr_min_bull = float(payload["rr_min_bull"])
    row.rr_min_bear = float(payload["rr_min_bear"])
    row.rr_min_range = float(payload["rr_min_range"])
    row.min_score_pct = float(payload["min_score_pct"])
    row.min_volume_24h_usdt_bull = float(payload["min_volume_24h_usdt_bull"])
    row.min_volume_24h_usdt_bear = float(payload["min_volume_24h_usdt_bear"])
    row.min_volume_24h_usdt_range = float(payload["min_volume_24h_usdt_range"])
    row.max_spread_bps_bull = float(payload["max_spread_bps_bull"])
    row.max_spread_bps_bear = float(payload["max_spread_bps_bear"])
    row.max_spread_bps_range = float(payload["max_spread_bps_range"])
    row.max_slippage_bps_bull = float(payload["max_slippage_bps_bull"])
    row.max_slippage_bps_bear = float(payload["max_slippage_bps_bear"])
    row.max_slippage_bps_range = float(payload["max_slippage_bps_range"])
    row.max_hold_minutes_bull = float(payload["max_hold_minutes_bull"])
    row.max_hold_minutes_bear = float(payload["max_hold_minutes_bear"])
    row.max_hold_minutes_range = float(payload["max_hold_minutes_range"])
    db.flush()
    return _to_dict(row)


def infer_market_regime(*, trend_score: float, atr_pct: float, momentum_score: float) -> tuple[str, str]:
    # Deterministic and explainable: trend + momentum define direction, ATR gates choppiness.
    t = float(trend_score or 0.0)
    m = float(momentum_score or 0.0)
    a = float(atr_pct or 0.0)
    if t == 0.0 and m == 0.0 and a == 0.0:
        return "bull", "legacy_default"
    directional = (0.7 * t) + (0.3 * m)
    if directional >= 0.25 and a <= 5.0:
        return "bull", "auto"
    if directional <= -0.25 and a <= 5.5:
        return "bear", "auto"
    return "range", "auto"
