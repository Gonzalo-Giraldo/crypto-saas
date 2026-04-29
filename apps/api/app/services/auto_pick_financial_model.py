from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def _decimal(value: Any, field_name: str) -> Decimal:
    try:
        out = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field_name}_invalid") from None
    if not out.is_finite():
        raise ValueError(f"{field_name}_not_finite")
    return out


def _clamp(value: Decimal, low: Decimal = Decimal("0"), high: Decimal = Decimal("1")) -> Decimal:
    if value < low:
        return low
    if value > high:
        return high
    return value


def _quantile(sorted_values: list[Decimal], percentile: Decimal) -> Decimal:
    if not sorted_values:
        raise ValueError("values_required")
    p = _clamp(percentile, Decimal("0"), Decimal("1"))
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = p * Decimal(len(sorted_values) - 1)
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - Decimal(lower)
    return sorted_values[lower] + ((sorted_values[upper] - sorted_values[lower]) * weight)


def calculate_support_resistance_by_percentiles(
    prices: list[Any],
    *,
    support_percentile: Any = "0.1",
    resistance_percentile: Any = "0.9",
) -> dict:
    """Calculate support/resistance from price percentiles using pure deterministic math."""
    clean = sorted(_decimal(price, "price") for price in prices)
    if not clean:
        raise ValueError("prices_required")
    support = _quantile(clean, _decimal(support_percentile, "support_percentile"))
    resistance = _quantile(clean, _decimal(resistance_percentile, "resistance_percentile"))
    if support <= 0 or resistance <= 0:
        raise ValueError("support_resistance_must_be_positive")
    if resistance < support:
        raise ValueError("resistance_below_support")
    return {
        "support": support,
        "resistance": resistance,
    }


def calculate_range_metrics(
    *,
    current_price: Any,
    support: Any,
    resistance: Any,
) -> dict:
    """Calculate range width, width percentage and normalized position inside range."""
    price = _decimal(current_price, "current_price")
    sup = _decimal(support, "support")
    res = _decimal(resistance, "resistance")
    if price <= 0 or sup <= 0 or res <= 0:
        raise ValueError("range_inputs_must_be_positive")
    if res <= sup:
        raise ValueError("invalid_range")
    range_width = res - sup
    range_pct = range_width / price
    position_in_range = _clamp((price - sup) / range_width)
    return {
        "range_width": range_width,
        "range_pct": range_pct,
        "position_in_range": position_in_range,
    }


def validate_range(
    *,
    support: Any,
    resistance: Any,
    current_price: Any,
    min_range_pct: Any = "0.002",
    max_range_pct: Any = "0.25",
) -> dict:
    """Fail closed when the detected range is invalid or not financially useful."""
    try:
        metrics = calculate_range_metrics(
            current_price=current_price,
            support=support,
            resistance=resistance,
        )
        min_pct = _decimal(min_range_pct, "min_range_pct")
        max_pct = _decimal(max_range_pct, "max_range_pct")
        if min_pct < 0 or max_pct <= 0 or max_pct < min_pct:
            raise ValueError("invalid_range_thresholds")
        range_pct = metrics["range_pct"]
        valid = min_pct <= range_pct <= max_pct
        reason = "range_valid" if valid else "range_pct_out_of_bounds"
        return {
            "valid": bool(valid),
            "reason": reason,
            **metrics,
        }
    except ValueError as exc:
        return {
            "valid": False,
            "reason": str(exc),
            "range_width": Decimal("0"),
            "range_pct": Decimal("0"),
            "position_in_range": Decimal("0"),
        }


def combine_trends(
    *,
    trend_swing: Any,
    trend_intraday: Any,
    swing_weight: Any = "0.65",
    intraday_weight: Any = "0.35",
) -> Decimal:
    """Combine swing and intraday trend scores into a normalized directional trend score."""
    swing = _clamp(_decimal(trend_swing, "trend_swing"), Decimal("-1"), Decimal("1"))
    intraday = _clamp(_decimal(trend_intraday, "trend_intraday"), Decimal("-1"), Decimal("1"))
    sw = _decimal(swing_weight, "swing_weight")
    iw = _decimal(intraday_weight, "intraday_weight")
    denom = sw + iw
    if denom <= 0:
        raise ValueError("trend_weights_invalid")
    return _clamp(((swing * sw) + (intraday * iw)) / denom, Decimal("-1"), Decimal("1"))


def calculate_structure_score(
    *,
    position_in_range: Any,
    combined_trend: Any,
    side: str,
) -> Decimal:
    """Score market structure using range location and trend alignment."""
    pos = _clamp(_decimal(position_in_range, "position_in_range"))
    trend = _clamp(_decimal(combined_trend, "combined_trend"), Decimal("-1"), Decimal("1"))
    side_norm = str(side or "").upper().strip()
    if side_norm not in {"BUY", "SELL"}:
        raise ValueError("side_must_be_buy_or_sell")

    if side_norm == "BUY":
        range_location_score = Decimal("1") - pos
        trend_score = (trend + Decimal("1")) / Decimal("2")
    else:
        range_location_score = pos
        trend_score = (Decimal("1") - trend) / Decimal("2")

    return _clamp((trend_score * Decimal("0.60")) + (range_location_score * Decimal("0.40")))


def calculate_confirmation_score(
    *,
    confirmations: dict[str, Any],
) -> dict:
    """Score weighted financial confirmations with conservative fail-closed defaults."""
    if not isinstance(confirmations, dict):
        raise ValueError("confirmations_must_be_dict")

    momentum = _clamp(_decimal(confirmations.get("momentum", "0"), "momentum"))
    volume = _clamp(_decimal(confirmations.get("volume", "0"), "volume"))
    micro = _clamp(_decimal(confirmations.get("micro", "0"), "micro"))
    atr_risk = _clamp(_decimal(confirmations.get("atr_risk", "1"), "atr_risk"))

    raw_score = (
        Decimal("0.40") * momentum
        + Decimal("0.25") * volume
        + Decimal("0.15") * micro
        - Decimal("0.20") * atr_risk
    )
    confirmation_score = _clamp(raw_score, Decimal("0"), Decimal("1"))
    confirmation_factor = _clamp(
        Decimal("1") + ((confirmation_score - Decimal("0.5")) * Decimal("0.40")),
        Decimal("0.70"),
        Decimal("1.20"),
    )

    return {
        "confirmation_score": confirmation_score,
        "confirmation_factor": confirmation_factor,
    }


def liquidity_factor_from_state(liquidity_state: str) -> Decimal:
    """Map liquidity state to a fail-closed factor."""
    state = str(liquidity_state or "").lower().strip()
    if state == "green":
        return Decimal("1")
    if state == "gray":
        return Decimal("0.75")
    return Decimal("0")


def calculate_final_score(
    *,
    structure_score: Any,
    confirmation_factor: Any,
    liquidity_factor: Any,
) -> Decimal:
    """Calculate final score without assuming production thresholds."""
    structure = _clamp(_decimal(structure_score, "structure_score"))
    confirmation = _decimal(confirmation_factor, "confirmation_factor")
    liquidity = _clamp(_decimal(liquidity_factor, "liquidity_factor"))
    if confirmation < 0:
        raise ValueError("confirmation_factor_invalid")
    return _clamp(structure * confirmation * liquidity)


def rank_candidates_by_final_score(candidates: list[dict]) -> list[dict]:
    """Return candidates sorted by final_score descending without side effects."""
    if not isinstance(candidates, list):
        raise ValueError("candidates_must_be_list")

    def _score(candidate: dict) -> Decimal:
        if not isinstance(candidate, dict):
            return Decimal("-1")
        try:
            return _decimal(candidate.get("final_score", "0"), "final_score")
        except ValueError:
            return Decimal("-1")

    return sorted(candidates, key=_score, reverse=True)
