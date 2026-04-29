from __future__ import annotations

from math import isfinite
from typing import Any


def _to_float(value: Any, field_name: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name}_invalid") from None
    if not isfinite(out):
        raise ValueError(f"{field_name}_not_finite")
    return out


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    value = _to_float(value, "value")
    return max(low, min(high, value))


def _percentile(values: list[Any], percentile: float) -> float:
    if not isinstance(values, list) or not values:
        raise ValueError("values_required")
    clean = sorted(_to_float(v, "value") for v in values)
    if any(v <= 0 for v in clean):
        raise ValueError("values_must_be_positive")
    p = _clamp(percentile, 0.0, 1.0)
    if len(clean) == 1:
        return clean[0]
    index = p * (len(clean) - 1)
    lower = int(index)
    upper = min(lower + 1, len(clean) - 1)
    weight = index - lower
    return clean[lower] + ((clean[upper] - clean[lower]) * weight)


def _require_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise ValueError("candidate_must_be_dict")
    symbol = str(candidate.get("symbol") or "").strip().upper()
    if not symbol:
        raise ValueError("symbol_required")
    ohlc = candidate.get("ohlc")
    if not isinstance(ohlc, dict):
        raise ValueError("ohlc_required")
    metrics = candidate.get("market_metrics")
    if not isinstance(metrics, dict):
        raise ValueError("market_metrics_required")
    return candidate


def _series(candidate: dict[str, Any], name: str) -> list[float]:
    raw = candidate.get("ohlc", {}).get(name)
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{name}_required")
    out = [_to_float(v, name) for v in raw]
    if any(v <= 0 for v in out):
        raise ValueError(f"{name}_must_be_positive")
    return out


def _metric(candidate: dict[str, Any], name: str) -> float:
    metrics = candidate.get("market_metrics", {})
    if name not in metrics:
        raise ValueError(f"{name}_required")
    return _to_float(metrics[name], name)


def evaluate_hard_filters(candidate: dict[str, Any]) -> dict[str, Any]:
    """Validate minimum crypto candidate inputs. Fail closed."""
    try:
        _require_candidate(candidate)
        lengths = {}
        for field in ("open", "high", "low", "close", "volume"):
            values = _series(candidate, field)
            lengths[field] = len(values)
        if len(set(lengths.values())) != 1:
            return {"valid": False, "reason": "ohlc_lengths_mismatch"}
        if lengths["close"] < 2:
            return {"valid": False, "reason": "ohlc_insufficient_history"}
        highs = _series(candidate, "high")
        lows = _series(candidate, "low")
        opens = _series(candidate, "open")
        closes = _series(candidate, "close")
        for idx, (open_, high, low, close) in enumerate(zip(opens, highs, lows, closes)):
            if high < low:
                return {"valid": False, "reason": f"high_below_low_at_{idx}"}
            if not low <= open_ <= high:
                return {"valid": False, "reason": f"open_out_of_range_at_{idx}"}
            if not low <= close <= high:
                return {"valid": False, "reason": f"close_out_of_range_at_{idx}"}
        liquidity_state = str(candidate.get("market_metrics", {}).get("liquidity_state") or "").lower().strip()
        if liquidity_state == "red":
            return {"valid": False, "reason": "liquidity_red"}
        if liquidity_state not in {"green", "gray"}:
            return {"valid": False, "reason": "liquidity_state_invalid"}
        for metric in ("momentum", "volume_relative", "atr_risk", "trend_swing", "trend_intraday"):
            _metric(candidate, metric)
        return {"valid": True, "reason": "ok"}
    except ValueError as exc:
        return {"valid": False, "reason": str(exc)}


def compute_structure(candidate: dict[str, Any]) -> dict[str, Any]:
    """Compute support, resistance and range position from real OHLC arrays."""
    _require_candidate(candidate)
    lows = _series(candidate, "low")
    highs = _series(candidate, "high")
    closes = _series(candidate, "close")
    support = _percentile(lows, 0.10)
    resistance = _percentile(highs, 0.90)
    price = closes[-1]
    if resistance <= support:
        return {
            "valid": False,
            "reason": "resistance_lte_support",
            "support": support,
            "resistance": resistance,
            "position_in_range": 0.0,
        }
    position = _clamp((price - support) / (resistance - support))
    return {
        "valid": True,
        "reason": "ok",
        "support": support,
        "resistance": resistance,
        "position_in_range": position,
    }


def compute_trend(candidate: dict[str, Any]) -> dict[str, Any]:
    """Compute combined trend where swing dominates and intraday only confirms."""
    _require_candidate(candidate)
    swing = _clamp(_metric(candidate, "trend_swing"), -1.0, 1.0)
    intraday = _clamp(_metric(candidate, "trend_intraday"), -1.0, 1.0)
    combined = ((0.65 * swing) + (0.35 * intraday)) / (0.65 + 0.35)
    combined = _clamp(combined, -1.0, 1.0)
    trend_score = (combined + 1.0) / 2.0
    return {
        "trend_swing": swing,
        "trend_intraday": intraday,
        "combined_trend": combined,
        "trend_score": _clamp(trend_score),
    }


def compute_confirmation(candidate: dict[str, Any]) -> dict[str, Any]:
    """Compute confirmation score and bounded confirmation factor."""
    _require_candidate(candidate)
    momentum = _clamp(_metric(candidate, "momentum"))
    volume = _clamp(_metric(candidate, "volume_relative"))
    micro = _clamp(_metric(candidate, "trend_intraday"), -1.0, 1.0)
    micro = (micro + 1.0) / 2.0
    atr = _clamp(_metric(candidate, "atr_risk"))

    confirmation_score = _clamp(
        (0.40 * momentum)
        + (0.25 * volume)
        + (0.15 * micro)
        - (0.20 * atr)
    )
    confirmation_factor = _clamp(
        1.0 + ((confirmation_score - 0.5) * 0.40),
        0.70,
        1.20,
    )
    return {
        "confirmation_score": confirmation_score,
        "confirmation_factor": confirmation_factor,
    }


def compute_liquidity(candidate: dict[str, Any]) -> dict[str, Any]:
    """Map liquidity state to fail-closed liquidity factor."""
    _require_candidate(candidate)
    state = str(candidate.get("market_metrics", {}).get("liquidity_state") or "").lower().strip()
    if state == "green":
        factor = 1.0
    elif state == "gray":
        factor = 0.75
    else:
        factor = 0.0
    return {
        "liquidity_state": state,
        "liquidity_factor": factor,
    }


def compute_final_score(candidate: dict[str, Any]) -> dict[str, Any]:
    """Evaluate full crypto Auto-Pick score. No fallback, no broker, no side effects."""
    symbol = str(candidate.get("symbol") or "").strip().upper() if isinstance(candidate, dict) else ""
    hard = evaluate_hard_filters(candidate)
    if not hard["valid"]:
        return {
            "symbol": symbol,
            "valid": False,
            "reason": hard["reason"],
            "support": 0.0,
            "resistance": 0.0,
            "position_in_range": 0.0,
            "combined_trend": 0.0,
            "structure_score": 0.0,
            "confirmation_score": 0.0,
            "confirmation_factor": 0.0,
            "liquidity_factor": 0.0,
            "final_score": 0.0,
        }

    structure = compute_structure(candidate)
    if not structure["valid"]:
        return {
            "symbol": symbol,
            "valid": False,
            "reason": structure["reason"],
            "support": float(structure["support"]),
            "resistance": float(structure["resistance"]),
            "position_in_range": 0.0,
            "combined_trend": 0.0,
            "structure_score": 0.0,
            "confirmation_score": 0.0,
            "confirmation_factor": 0.0,
            "liquidity_factor": 0.0,
            "final_score": 0.0,
        }

    trend = compute_trend(candidate)
    confirmation = compute_confirmation(candidate)
    liquidity = compute_liquidity(candidate)

    range_score = 1.0 - float(structure["position_in_range"])
    structure_score = _clamp(
        (0.60 * float(trend["trend_score"]))
        + (0.40 * range_score)
    )
    final_score = _clamp(
        structure_score
        * float(confirmation["confirmation_factor"])
        * float(liquidity["liquidity_factor"])
    )

    return {
        "symbol": symbol,
        "valid": bool(final_score > 0.0),
        "reason": "ok" if final_score > 0.0 else "final_score_zero",
        "support": float(structure["support"]),
        "resistance": float(structure["resistance"]),
        "position_in_range": float(structure["position_in_range"]),
        "combined_trend": float(trend["combined_trend"]),
        "structure_score": float(structure_score),
        "confirmation_score": float(confirmation["confirmation_score"]),
        "confirmation_factor": float(confirmation["confirmation_factor"]),
        "liquidity_factor": float(liquidity["liquidity_factor"]),
        "final_score": float(final_score),
    }


def rank_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank valid crypto candidates by final_score descending."""
    if not isinstance(candidates, list):
        raise ValueError("candidates_must_be_list")
    evaluated = [compute_final_score(candidate) for candidate in candidates]
    valid = [row for row in evaluated if bool(row.get("valid"))]
    return sorted(valid, key=lambda row: float(row["final_score"]), reverse=True)
