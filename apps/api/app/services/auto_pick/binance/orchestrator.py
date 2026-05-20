from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List

from apps.api.app.services.auto_pick.contracts import (
    AutoPickCandidateProjection,
    AutoPickDecision,
    AutoPickNoTrade,
    AutoPickObservationReport,
    AutoPickResult,
)

from apps.api.app.services.auto_pick.binance.market_data import (
    fetch_ticker_24h_rows,
    fetch_1h_klines,
    fetch_15m_klines,
)

from apps.api.app.services.auto_pick.binance.universe import (
    build_candidate_symbols,
)

from apps.api.app.services.auto_pick_binance_input_adapter_v1 import (
    build_crypto_model_input,
)

from apps.api.app.services.auto_pick_binance_model_v1 import (
    compute_final_score,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None

def _empty_report(
    *,
    status: str,
    reason: str,
    top_n: int,
    started_at: str,
    rejected_candidates: list[dict[str, Any]] | None = None,
) -> AutoPickObservationReport:
    return AutoPickObservationReport(
        decision_status=status,
        broker="BINANCE",
        reason=reason,
        no_selection_reason=reason,
        selected=None,
        selected_symbol=None,
        selected_rank=None,
        ranked_count=0,
        top_n=int(top_n),
        candidates=[],
        rejected_candidates=list(rejected_candidates or []),
        started_at=started_at,
        finished_at=_utc_now_iso(),
        production_priority=True,
    )


def _candidate_projection(
    *,
    evaluation: dict[str, Any],
    rank: int,
    selected: bool,
) -> AutoPickCandidateProjection:
    candidate = evaluation.get("_candidate") or {}
    return AutoPickCandidateProjection(
        rank=int(rank),
        symbol=evaluation.get("symbol"),
        side=evaluation.get("side"),
        valid=bool(evaluation.get("valid")),
        reason=evaluation.get("reason"),
        final_score=_safe_float(evaluation.get("final_score")),
        selected=bool(selected),
        entry_price_reference=_safe_float(candidate.get("entry_price")),
        features={
            "support": _safe_float(evaluation.get("support")),
            "resistance": _safe_float(evaluation.get("resistance")),
            "position_in_range": _safe_float(evaluation.get("position_in_range")),
            "combined_trend": _safe_float(evaluation.get("combined_trend")),
            "structure_score": _safe_float(evaluation.get("structure_score")),
            "confirmation_score": _safe_float(evaluation.get("confirmation_score")),
            "confirmation_factor": _safe_float(evaluation.get("confirmation_factor")),
            "liquidity_factor": _safe_float(evaluation.get("liquidity_factor")),
        },
    )


def run_binance_auto_pick_observation(
    *,
    top_n: int = 10,
    max_symbols: int | None = None,
) -> AutoPickObservationReport:
    """
    Autonomous Auto-Pick observation pipeline.

    This function:
    - reads Binance market data
    - builds candidates
    - computes the approved Auto-Pick score
    - ranks candidates
    - returns selection or no-selection projection

    It does NOT:
    - call Risk
    - create Intent
    - touch DB
    - execute broker orders
    - change Auto-Pick math
    """

    started_at = _utc_now_iso()

    try:
        ticker_rows = fetch_ticker_24h_rows()
        if not ticker_rows:
            return _empty_report(
                status="NO_SELECTION",
                reason="no_ticker_data",
                top_n=top_n,
                started_at=started_at,
            )

        symbols = build_candidate_symbols(ticker_rows)
        if max_symbols is not None:
            symbols = symbols[: max(0, int(max_symbols))]

        if not symbols:
            return _empty_report(
                status="NO_SELECTION",
                reason="no_symbols",
                top_n=top_n,
                started_at=started_at,
            )

        evaluations: List[dict[str, Any]] = []
        rejected_candidates: List[dict[str, Any]] = []

        for symbol in symbols:
            ticker = next((r for r in ticker_rows if r.get("symbol") == symbol), None)
            if not ticker:
                rejected_candidates.append({
                    "symbol": symbol,
                    "reason": "missing_ticker",
                })
                continue

            klines_1h = fetch_1h_klines(symbol)
            klines_15m = fetch_15m_klines(symbol)

            if not klines_1h:
                rejected_candidates.append({
                    "symbol": symbol,
                    "reason": "missing_1h_klines",
                })
                continue

            if not klines_15m:
                rejected_candidates.append({
                    "symbol": symbol,
                    "reason": "missing_15m_klines",
                })
                continue

            try:
                candidate = build_crypto_model_input(
                    symbol=symbol,
                    klines_1h=klines_1h,
                    klines_15m=klines_15m,
                    ticker_24h=ticker,
                )
                evaluation = compute_final_score(candidate)

                if not evaluation.get("valid"):
                    rejected_candidates.append({
                        "symbol": symbol,
                        "reason": "invalid_evaluation",
                    })
                    continue

            except Exception:
                rejected_candidates.append({
                    "symbol": symbol,
                    "reason": "candidate_build_failed",
                })
                continue

            evaluation["_candidate"] = candidate

            side = str(evaluation.get("side") or "").upper().strip()

            if side not in {"BUY", "SELL"}:
                rejected_candidates.append({
                    "symbol": symbol,
                    "reason": "invalid_side",
                })
                continue

            evaluation["side"] = side
            evaluations.append(evaluation)

        if not evaluations:
            return _empty_report(
                status="NO_SELECTION",
                reason="no_valid_candidates",
                top_n=top_n,
                started_at=started_at,
                rejected_candidates=rejected_candidates,
            )

        ranked = sorted(
            evaluations,
            key=lambda row: row.get("final_score", 0),
            reverse=True,
        )

        top_limit = max(1, int(top_n))
        projected_candidates = [
            _candidate_projection(
                evaluation=row,
                rank=idx + 1,
                selected=(idx == 0),
            )
            for idx, row in enumerate(ranked[:top_limit])
        ]

        selected_projection = projected_candidates[0] if projected_candidates else None

        return AutoPickObservationReport(
            decision_status="SELECTED",
            broker="BINANCE",
            reason="selected_top_ranked_candidate",
            no_selection_reason=None,
            selected=selected_projection,
            selected_symbol=selected_projection.symbol if selected_projection else None,
            selected_rank=1 if selected_projection else None,
            ranked_count=len(ranked),
            top_n=int(top_n),
            candidates=projected_candidates,
            rejected_candidates=rejected_candidates,
            started_at=started_at,
            finished_at=_utc_now_iso(),
            production_priority=True,
        )

    except Exception:
        return _empty_report(
            status="CONTRACT_FAILED",
            reason="orchestrator_failure",
            top_n=top_n,
            started_at=started_at,
        )


def run_binance_auto_pick(*, payload: dict[str, Any] | None = None) -> AutoPickResult:
    report = run_binance_auto_pick_observation(top_n=10)

    if report.decision_status != "SELECTED":
        return AutoPickNoTrade(
            broker="BINANCE",
            reason=str(report.no_selection_reason or report.reason or "no_valid_candidates"),
            evidence={
                "decision_status": report.decision_status,
                "ranked_count": report.ranked_count,
            },
        )

    selected = report.selected
    if selected is None:
        return AutoPickNoTrade(
            broker="BINANCE",
            reason="missing_selected_candidate",
            evidence={"decision_status": report.decision_status},
        )

    side = str(selected.side or "").upper().strip()
    if side not in {"BUY", "SELL"}:
        return AutoPickNoTrade(
            broker="BINANCE",
            reason="side_invalid",
            evidence={"selected": selected.to_dict()},
        )

    entry_price_f = selected.entry_price_reference
    if entry_price_f is None:
        return AutoPickNoTrade(
            broker="BINANCE",
            reason="missing_entry_price_reference",
            evidence={"selected": selected.to_dict()},
        )

    if entry_price_f <= 0:
        return AutoPickNoTrade(
            broker="BINANCE",
            reason="non_positive_entry_price_reference",
            evidence={"selected": selected.to_dict()},
        )

    return AutoPickDecision(
        symbol=selected.symbol,
        side=side,
        direction="LONG" if side == "BUY" else "SHORT",
        broker="BINANCE",
        asset_profile="CRYPTO",
        model_version="binance_auto_pick_pipeline_v1",
        final_score=float(selected.final_score or 0),
        decision_reason="selected_top_ranked_candidate",
        evidence={
            "ranked_count": int(report.ranked_count),
            "selected_rank": 1,
            "entry_price_reference": float(entry_price_f),
            "entry_price_source": "ticker.lastPrice",
            "entry_price_semantics": "reference_only_not_fill",
        },
    )
