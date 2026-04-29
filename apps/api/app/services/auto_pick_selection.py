from __future__ import annotations

from typing import Any

from apps.api.app.api.ops import (
    _build_auto_pick_universe,
    _pretrade_scores,
    _blend_learning_score,
    _classify_liquidity_state,
    _compute_binance_mtf_signal,
    _ibkr_fallback_symbols,
)
def _resolve_auto_pick_mtf_trend_fields(
    symbol: Optional[str],
    candidate_obj: Optional[PretradeCheckRequest],
    exchange: str,
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
    trend = float(candidate_obj.market_trend_score) if candidate_obj else None
    trend_1d = (
        float(candidate_obj.market_trend_score_1d)
        if candidate_obj and candidate_obj.market_trend_score_1d is not None
        else None
    )
    trend_4h = (
        float(candidate_obj.market_trend_score_4h)
        if candidate_obj and candidate_obj.market_trend_score_4h is not None
        else None
    )
    trend_1h = (
        float(candidate_obj.market_trend_score_1h)
        if candidate_obj and candidate_obj.market_trend_score_1h is not None
        else None
    )
    micro_15m = (
        float(candidate_obj.market_micro_trend_15m)
        if candidate_obj and candidate_obj.market_micro_trend_15m is not None
        else None
    )
    # For BINANCE, fill missing MTF fields directly from klines signal when snapshots
    # only provided aggregate trend_score.
    if (exchange or "").upper() == "BINANCE" and symbol and (
        trend is None or trend_1d is None or trend_4h is None or trend_1h is None or micro_15m is None
    ):
        try:
            mtf = _compute_binance_mtf_signal(str(symbol).upper())
        except Exception:
            mtf = None
        if mtf:
            if trend is None:
                trend = float(mtf.get("trend_score") or 0.0)
            if trend_1d is None and mtf.get("trend_1d") is not None:
                trend_1d = float(mtf.get("trend_1d"))
            if trend_4h is None and mtf.get("trend_4h") is not None:
                trend_4h = float(mtf.get("trend_4h"))
            if trend_1h is None and mtf.get("trend_1h") is not None:
                trend_1h = float(mtf.get("trend_1h"))
            if micro_15m is None and mtf.get("micro_trend_15m") is not None:
                micro_15m = float(mtf.get("micro_trend_15m"))
    return trend, trend_1d, trend_4h, trend_1h, micro_15m

def _select_auto_pick_candidate(
    *,
    db: Session,
    current_user: User,
    exchange: str,
    payload: PretradeAutoPickRequest,
    runtime_policy: dict,
    min_score_pct: float,
    score_weight_rules: float,
    score_weight_market: float,
) -> dict:
    # Respect explicit candidates when provided (tests/manual overrides).
    # Otherwise use the broker universe from market monitor snapshots.
    universe = list(payload.candidates or [])
    if not universe:
        universe = _build_auto_pick_universe(
            exchange,
            db=db,
            tenant_id=_tenant_id(current_user),
            direction=payload.direction,
        )
    scan_payload = PretradeScanRequest(
        candidates=universe,
        # Auto-pick evaluates the full broker universe each tick.
        top_n=max(1, len(universe)),
        include_blocked=True,
    )
    scan = _scan_pretrade_candidates(
        db=db,
        current_user=current_user,
        exchange=exchange,
        payload=scan_payload,
        score_weight_rules=score_weight_rules,
        score_weight_market=score_weight_market,
    )
    candidate_by_symbol = {c.symbol.upper(): c for c in universe}
    assets = scan.get("assets", [])
    top_candidate = assets[0] if assets else None
    top_candidate_symbol = (top_candidate or {}).get("symbol")
    top_candidate_obj = (
        candidate_by_symbol.get(str(top_candidate_symbol).upper())
        if top_candidate_symbol
        else None
    )
    (
        top_candidate_trend_score,
        top_candidate_trend_score_1d,
        top_candidate_trend_score_4h,
        top_candidate_trend_score_1h,
        top_candidate_micro_trend_15m,
    ) = _resolve_auto_pick_mtf_trend_fields(top_candidate_symbol, top_candidate_obj, exchange)
    avg_score = None
    avg_score_base = None
    avg_score_rules = None
    avg_score_market = None
    if assets:
        avg_score = round(sum(float(a.get("score") or 0.0) for a in assets) / len(assets), 2)
        avg_score_base = round(sum(float(a.get("score_base") or a.get("score") or 0.0) for a in assets) / len(assets), 2)
        avg_score_rules = round(sum(float(a.get("score_rules") or 0.0) for a in assets) / len(assets), 2)
        avg_score_market = round(sum(float(a.get("score_market") or 0.0) for a in assets) / len(assets), 2)

    if not universe:
        return {
            "universe": universe,
            "scan": scan,
            "candidate_by_symbol": candidate_by_symbol,
            "top_candidate": top_candidate,
            "top_candidate_symbol": top_candidate_symbol,
            "top_candidate_trend_score": top_candidate_trend_score,
            "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
            "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
            "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
            "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
            "avg_score": avg_score,
            "avg_score_base": avg_score_base,
            "avg_score_rules": avg_score_rules,
            "avg_score_market": avg_score_market,
            "early_response": {
                "exchange": exchange,
                "dry_run": bool(payload.dry_run),
                "requested_direction": payload.direction,
                "selected": False,
                "selected_symbol": None,
                "selected_side": None,
                "selected_qty": None,
                "selected_score": None,
                "selected_score_rules": None,
                "selected_score_market": None,
                "selected_trend_score": None,
                "selected_trend_score_1d": None,
                "selected_trend_score_4h": None,
                "selected_trend_score_1h": None,
                "selected_micro_trend_15m": None,
                "selected_market_regime": None,
                "top_candidate_symbol": None,
                "top_candidate_score": None,
                "top_candidate_score_rules": None,
                "top_candidate_score_market": None,
                "top_candidate_trend_score": None,
                "top_candidate_trend_score_1d": None,
                "top_candidate_trend_score_4h": None,
                "top_candidate_trend_score_1h": None,
                "top_candidate_micro_trend_15m": None,
                "avg_score": None,
                "avg_score_rules": None,
                "avg_score_market": None,
                "decision": "no_universe_symbols_configured",
                "top_failed_checks": ["allowlist_empty"],
                "execution": None,
                "scan": scan,
            },
            "early_finalize_kwargs": {},
        }

    passed_assets = [a for a in assets if bool(a.get("passed"))]
    score_eligible = [
        a
        for a in passed_assets
        if float(a.get("score") or 0.0)
        >= score_threshold_for_side(
            min_score_pct=float(min_score_pct),
            side=str(a.get("side") or "BUY"),
        )
    ]
    if not score_eligible:
        top_failed_checks: list[str] = []
        if assets:
            top_failed_checks = list(assets[0].get("failed_checks") or [])
        if passed_assets and "score_below_min_threshold" not in top_failed_checks:
            top_failed_checks = ["score_below_min_threshold", *top_failed_checks]
        return {
            "universe": universe,
            "scan": scan,
            "candidate_by_symbol": candidate_by_symbol,
            "top_candidate": top_candidate,
            "top_candidate_symbol": top_candidate_symbol,
            "top_candidate_trend_score": top_candidate_trend_score,
            "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
            "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
            "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
            "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
            "avg_score": avg_score,
            "avg_score_base": avg_score_base,
            "avg_score_rules": avg_score_rules,
            "avg_score_market": avg_score_market,
            "early_response": {
                "exchange": exchange,
                "dry_run": bool(payload.dry_run),
                "requested_direction": payload.direction,
                "selected": False,
                "selected_symbol": None,
                "selected_side": None,
                "selected_qty": None,
                "selected_score": None,
                "selected_score_rules": None,
                "selected_score_market": None,
                "selected_trend_score": None,
                "selected_trend_score_1d": None,
                "selected_trend_score_4h": None,
                "selected_trend_score_1h": None,
                "selected_micro_trend_15m": None,
                "selected_market_regime": None,
                "top_candidate_symbol": top_candidate_symbol,
                "top_candidate_score": (top_candidate or {}).get("score"),
                "top_candidate_score_base": (top_candidate or {}).get("score_base"),
                "top_candidate_score_rules": (top_candidate or {}).get("score_rules"),
                "top_candidate_score_market": (top_candidate or {}).get("score_market"),
                "top_candidate_learning_prob_hit_pct": (top_candidate or {}).get("learning_prob_hit_pct"),
                "top_candidate_learning_samples": (top_candidate or {}).get("learning_samples"),
                "top_candidate_learning_score": (top_candidate or {}).get("learning_score"),
                "top_candidate_learning_delta_points": (top_candidate or {}).get("learning_delta_points"),
                "top_candidate_trend_score": top_candidate_trend_score,
                "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
                "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
                "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
                "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
                "avg_score": avg_score,
                "avg_score_base": avg_score_base,
                "avg_score_rules": avg_score_rules,
                "avg_score_market": avg_score_market,
                "decision": "no_candidate_passed",
                "top_failed_checks": top_failed_checks,
                "execution": None,
                "scan": scan,
            },
            "early_finalize_kwargs": {},
        }

    selected = score_eligible[0]
    regime = str(selected.get("market_regime") or "range")
    max_spread = float(runtime_policy.get(f"max_spread_bps_{regime}", 15.0))
    max_slippage = float(runtime_policy.get(f"max_slippage_bps_{regime}", 20.0))
    candidate = candidate_by_symbol.get(str(selected.get("symbol") or "").upper())
    cand_spread = float(candidate.spread_bps) if candidate else max_spread
    cand_slippage = float(candidate.slippage_bps) if candidate else max_slippage
    selected_score = float(selected.get("score") or 0.0)
    liquidity_state, size_multiplier = _classify_liquidity_state(
        spread_bps=cand_spread,
        slippage_bps=cand_slippage,
        max_spread_bps=max_spread,
        max_slippage_bps=max_slippage,
        selected_score=selected_score,
        min_score_pct=min_score_pct,
    )
    selected_side = str(selected.get("side") or "BUY").upper()
    if selected_side == "SELL" and liquidity_state != "green":
        return {
            "universe": universe,
            "scan": scan,
            "candidate_by_symbol": candidate_by_symbol,
            "top_candidate": top_candidate,
            "top_candidate_symbol": top_candidate_symbol,
            "top_candidate_trend_score": top_candidate_trend_score,
            "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
            "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
            "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
            "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
            "avg_score": avg_score,
            "avg_score_base": avg_score_base,
            "avg_score_rules": avg_score_rules,
            "avg_score_market": avg_score_market,
            "early_response": {
                "exchange": exchange,
                "dry_run": bool(payload.dry_run),
                "requested_direction": payload.direction,
                "selected": False,
                "selected_symbol": None,
                "selected_side": None,
                "selected_qty": None,
                "selected_score": None,
                "selected_score_rules": None,
                "selected_score_market": None,
                "selected_trend_score": None,
                "selected_trend_score_1d": None,
                "selected_trend_score_4h": None,
                "selected_trend_score_1h": None,
                "selected_micro_trend_15m": None,
                "selected_market_regime": None,
                "selected_liquidity_state": liquidity_state,
                "selected_size_multiplier": 0.0,
                "top_candidate_symbol": top_candidate_symbol,
                "top_candidate_score": (top_candidate or {}).get("score"),
                "top_candidate_score_rules": (top_candidate or {}).get("score_rules"),
                "top_candidate_score_market": (top_candidate or {}).get("score_market"),
                "top_candidate_trend_score": top_candidate_trend_score,
                "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
                "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
                "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
                "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
                "avg_score": avg_score,
                "avg_score_rules": avg_score_rules,
                "avg_score_market": avg_score_market,
                "decision": "no_candidate_passed",
                "top_failed_checks": ["short_requires_green_liquidity"],
                "execution": None,
                "scan": scan,
            },
            "early_finalize_kwargs": {"max_spread": max_spread, "max_slippage": max_slippage},
        }
    if liquidity_state == "red":
        return {
            "universe": universe,
            "scan": scan,
            "candidate_by_symbol": candidate_by_symbol,
            "top_candidate": top_candidate,
            "top_candidate_symbol": top_candidate_symbol,
            "top_candidate_trend_score": top_candidate_trend_score,
            "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
            "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
            "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
            "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
            "avg_score": avg_score,
            "avg_score_base": avg_score_base,
            "avg_score_rules": avg_score_rules,
            "avg_score_market": avg_score_market,
            "early_response": {
                "exchange": exchange,
                "dry_run": bool(payload.dry_run),
                "requested_direction": payload.direction,
                "selected": False,
                "selected_symbol": None,
                "selected_side": None,
                "selected_qty": None,
                "selected_score": None,
                "selected_score_rules": None,
                "selected_score_market": None,
                "selected_trend_score": None,
                "selected_trend_score_1d": None,
                "selected_trend_score_4h": None,
                "selected_trend_score_1h": None,
                "selected_micro_trend_15m": None,
                "selected_market_regime": None,
                "selected_liquidity_state": "red",
                "selected_size_multiplier": 0.0,
                "top_candidate_symbol": top_candidate_symbol,
                "top_candidate_score": (top_candidate or {}).get("score"),
                "top_candidate_score_rules": (top_candidate or {}).get("score_rules"),
                "top_candidate_score_market": (top_candidate or {}).get("score_market"),
                "top_candidate_trend_score": top_candidate_trend_score,
                "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
                "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
                "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
                "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
                "avg_score": avg_score,
                "avg_score_rules": avg_score_rules,
                "avg_score_market": avg_score_market,
                "decision": "no_candidate_passed",
                "top_failed_checks": ["effective_liquidity_failed"],
                "execution": None,
                "scan": scan,
            },
            "early_finalize_kwargs": {"max_spread": max_spread, "max_slippage": max_slippage},
        }

    selected_qty_requested = float(selected["qty"])
    selected_qty = selected_qty_requested * float(size_multiplier)
    if selected_qty <= 0:
        selected_qty = selected_qty_requested
    if selected_side == "SELL":
        selected_qty = selected_qty * 0.35
        size_multiplier = float(size_multiplier) * 0.35

    selected_qty_sized = float(selected_qty)
    selected_symbol = str(selected["symbol"])

    return {
        "universe": universe,
        "scan": scan,
        "candidate_by_symbol": candidate_by_symbol,
        "top_candidate": top_candidate,
        "top_candidate_symbol": top_candidate_symbol,
        "top_candidate_trend_score": top_candidate_trend_score,
        "top_candidate_trend_score_1d": top_candidate_trend_score_1d,
        "top_candidate_trend_score_4h": top_candidate_trend_score_4h,
        "top_candidate_trend_score_1h": top_candidate_trend_score_1h,
        "top_candidate_micro_trend_15m": top_candidate_micro_trend_15m,
        "avg_score": avg_score,
        "avg_score_base": avg_score_base,
        "avg_score_rules": avg_score_rules,
        "avg_score_market": avg_score_market,
        "early_response": None,
        "early_finalize_kwargs": {},
        "selected": selected,
        "candidate": candidate,
        "max_spread": max_spread,
        "max_slippage": max_slippage,
        "liquidity_state": liquidity_state,
        "size_multiplier": size_multiplier,
        "selected_side": selected_side,
        "selected_qty_requested": selected_qty_requested,
        "selected_qty": selected_qty,
        "selected_qty_sized": selected_qty_sized,
        "selected_symbol": selected_symbol,
    }
