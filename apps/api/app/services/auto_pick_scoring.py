from __future__ import annotations
def _pretrade_scores(
    result: dict,
    payload: PretradeCheckRequest,
    *,
    score_weight_rules: float = 0.4,
    score_weight_market: float = 0.6,
) -> tuple[float, float, float]:
    checks = result.get("checks", [])
    total = max(1, len(checks))
    passed_count = sum(1 for c in checks if bool(c.get("passed")))
    ratio = passed_count / total
    score_rules = ratio * 100.0

    trend_raw = max(-1.0, min(1.0, float(payload.market_trend_score)))
    momentum_raw = max(-1.0, min(1.0, float(payload.momentum_score)))
    micro_raw = payload.market_micro_trend_15m
    micro_raw = 0.0 if micro_raw is None else max(-1.0, min(1.0, float(micro_raw)))
    side = str(payload.side or "BUY").upper()
    # For SHORT candidates, negative trend/momentum should increase score.
    trend = trend_raw if side == "BUY" else (-trend_raw)
    momentum = momentum_raw if side == "BUY" else (-momentum_raw)
    micro = micro_raw if side == "BUY" else (-micro_raw)
    rr = max(0.0, min(3.0, float(payload.rr_estimate)))
    spread = max(0.0, float(payload.spread_bps))
    slippage = max(0.0, float(payload.slippage_bps))
    atr_pct = max(0.0, float(payload.atr_pct))
    vol_24h = max(0.0, float(payload.volume_24h_usdt))
    liq = min(1.0, vol_24h / 200_000_000.0)
    atr_penalty = max(0.0, atr_pct - 6.0) * 1.5

    score_market = 45.0
    score_market += trend * 16.0
    score_market += momentum * 14.0
    # Micro trend is confirmation only; dampen impact in noisy volatility.
    micro_mult = 0.6 if atr_pct > 6.0 else 1.0
    score_market += micro * 4.0 * micro_mult
    score_market += rr * 7.0
    score_market += liq * 10.0
    score_market -= spread * 0.6
    score_market -= slippage * 0.55
    score_market -= atr_penalty
    score_market = max(0.0, min(100.0, score_market))

    w_rules = max(0.0, float(score_weight_rules))
    w_market = max(0.0, float(score_weight_market))
    denom = max(0.0001, w_rules + w_market)
    score_final = ((w_rules * score_rules) + (w_market * score_market)) / denom
    score_final = max(0.0, min(100.0, score_final))
    return round(score_rules, 2), round(score_market, 2), round(score_final, 2)

def _blend_learning_score(score_base: float, learning_score: Optional[float]) -> tuple[float, float]:
    base = max(0.0, min(100.0, float(score_base)))
    if learning_score is None:
        return round(base, 2), 0.0
    rules_w = max(0.0, float(settings.LEARNING_DECISION_RULES_WEIGHT or 0.9))
    model_w = max(0.0, float(settings.LEARNING_DECISION_MODEL_WEIGHT or 0.1))
    denom = max(0.0001, rules_w + model_w)
    raw_blend = ((rules_w * base) + (model_w * float(learning_score))) / denom
    raw_delta = raw_blend - base
    max_delta = max(0.0, float(settings.LEARNING_DECISION_MAX_DELTA_POINTS or 6.0))
    delta = max(-max_delta, min(max_delta, raw_delta))
    final = max(0.0, min(100.0, base + delta))
    return round(final, 2), round(delta, 2)

def _classify_liquidity_state(
    *,
    spread_bps: float,
    slippage_bps: float,
    max_spread_bps: float,
    max_slippage_bps: float,
    selected_score: float,
    min_score_pct: float,
) -> tuple[str, float]:
    # Green: strong margin vs limits and score comfortably above threshold.
    green = (
        spread_bps <= (0.80 * max_spread_bps)
        and slippage_bps <= (0.80 * max_slippage_bps)
        and selected_score >= (min_score_pct + 2.0)
    )
    if green:
        return "green", 1.0
    # Gray: still tradable but with tighter edge; reduce size.
    gray = (
        spread_bps <= max_spread_bps
        and slippage_bps <= max_slippage_bps
        and selected_score >= min_score_pct
    )
    if gray:
        return "gray", 0.5
    return "red", 0.0
