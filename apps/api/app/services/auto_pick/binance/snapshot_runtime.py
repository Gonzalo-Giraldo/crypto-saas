from __future__ import annotations

from typing import Any

from apps.api.app.services.auto_pick.binance.observation_contracts import (
    BinanceMarketObservationSnapshot,
)
from apps.api.app.services.auto_pick.binance.universe import build_candidate_symbols
from apps.api.app.services.auto_pick_binance_input_adapter_v1 import build_crypto_model_input
from apps.api.app.services.auto_pick_binance_model_v1 import compute_final_score
from apps.api.app.services.auto_pick.binance.orchestrator import (
    AutoPickCandidateProjection,
    AutoPickObservationReport,
)


def extract_snapshot_market_context(snapshot: BinanceMarketObservationSnapshot) -> dict[str, Any]:
    """
    Build read-only market context from an immutable observation snapshot.

    This does not:
    - fetch Binance
    - touch DB
    - score candidates
    - call Risk/Intent
    - mutate runtime state
    """

    ticker_rows: list[dict[str, Any]] = []
    klines_1h: dict[str, list[list[Any]]] = {}
    klines_15m: dict[str, list[list[Any]]] = {}

    for read in snapshot.reads:
      if read.status != "OK":
          continue

      if read.source_type == "ticker_24h":
          ticker_rows.extend(row for row in read.rows if isinstance(row, dict))
          continue

      if read.source_type == "klines":
          symbol = str(read.symbol or "").upper().strip()
          if not symbol:
              continue

          rows = [row for row in read.rows if isinstance(row, list)]

          if read.interval == "1h":
              klines_1h[symbol] = rows
              continue

          if read.interval == "15m":
              klines_15m[symbol] = rows

    return {
        "ticker_rows": ticker_rows,
        "klines_1h": klines_1h,
        "klines_15m": klines_15m,
    }

def _no_selection_report(
    *,
    reason: str,
    top_n: int,
    rejected_candidates: list[dict[str, str]] | None = None,
) -> AutoPickObservationReport:
    return AutoPickObservationReport(
        decision_status="NO_SELECTION",
        broker="BINANCE",
        reason=reason,
        no_selection_reason=reason,
        selected=None,
        selected_symbol=None,
        selected_rank=None,
        ranked_count=0,
        top_n=top_n,
        candidates=[],
        rejected_candidates=list(rejected_candidates or []),
        production_priority=True,
    )


def run_binance_auto_pick_observation_from_snapshot(
    snapshot: BinanceMarketObservationSnapshot,
    *,
    top_n: int = 10,
    max_symbols: int | None = None,
) -> AutoPickObservationReport:
    """
    Run Auto-pick observation deterministically from an immutable snapshot.

    This function must not:
    - fetch Binance
    - touch DB
    - call Risk/Intent
    - execute broker mutations
    - change scoring math
    """

    context = extract_snapshot_market_context(snapshot)
    ticker_rows = context["ticker_rows"]

    if not ticker_rows:
        return _no_selection_report(reason="no_ticker_data", top_n=top_n)

    symbols = build_candidate_symbols(ticker_rows)
    if max_symbols is not None:
        symbols = symbols[: int(max_symbols)]

    if not symbols:
        return _no_selection_report(reason="no_candidate_symbols", top_n=top_n)

    klines_1h_by_symbol = context["klines_1h"]
    klines_15m_by_symbol = context["klines_15m"]

    evaluated: list[dict[str, Any]] = []
    rejected_candidates: list[dict[str, str]] = []

    for symbol in symbols:
        ticker = next((row for row in ticker_rows if row.get("symbol") == symbol), None)
        if not ticker:
            rejected_candidates.append({"symbol": symbol, "reason": "missing_ticker"})
            continue

        klines_1h = klines_1h_by_symbol.get(symbol) or []
        klines_15m = klines_15m_by_symbol.get(symbol) or []

        if not klines_1h:
            rejected_candidates.append({"symbol": symbol, "reason": "missing_1h_klines"})
            continue

        if not klines_15m:
            rejected_candidates.append({"symbol": symbol, "reason": "missing_15m_klines"})
            continue

        try:
            candidate_input = build_crypto_model_input(
                symbol=symbol,
                klines_1h=klines_1h,
                klines_15m=klines_15m,
                ticker_24h=ticker,
            )
            score = compute_final_score(candidate_input)
        except Exception as exc:
            rejected_candidates.append({
                "symbol": symbol,
                "reason": f"candidate_input_exception:{str(exc) or exc.__class__.__name__}",
            })
            continue

        if score.get("valid"):
            evaluated.append(
                {
                    **score,
                    "entry_price_reference": candidate_input.get("entry_price"),
                    "features": {
                        **candidate_input.get("market_metrics", {}),
                        "support": score.get("support"),
                        "resistance": score.get("resistance"),
                        "position_in_range": score.get("position_in_range"),
                        "combined_trend": score.get("combined_trend"),
                        "structure_score": score.get("structure_score"),
                        "confirmation_score": score.get("confirmation_score"),
                        "confirmation_factor": score.get("confirmation_factor"),
                        "liquidity_factor": score.get("liquidity_factor"),
                    },
                }
            )
        else:
            rejected_candidates.append({
                "symbol": symbol,
                "reason": str(score.get("reason") or "invalid_score"),
            })

    ranked = sorted(
        evaluated,
        key=lambda row: float(row.get("final_score") or 0.0),
        reverse=True,
    )

    if not ranked:
        return _no_selection_report(
            reason="no_valid_candidates",
            top_n=top_n,
            rejected_candidates=rejected_candidates,
        )

    selected_symbol = str(ranked[0]["symbol"])
    projections: list[AutoPickCandidateProjection] = []

    for idx, row in enumerate(ranked[: int(top_n)], start=1):
        projections.append(
            AutoPickCandidateProjection(
                rank=idx,
                symbol=str(row["symbol"]),
                side=str(row.get("side") or ""),
                valid=bool(row.get("valid")),
                reason=str(row.get("reason") or "ok"),
                final_score=float(row.get("final_score") or 0.0),
                selected=str(row["symbol"]) == selected_symbol,
                entry_price_reference=row.get("entry_price_reference"),
                features=dict(row.get("features") or {}),
            )
        )

    selected = projections[0]

    return AutoPickObservationReport(
        decision_status="SELECTED",
        broker="BINANCE",
        reason="selected_top_ranked_candidate",
        no_selection_reason=None,
        selected=selected,
        selected_symbol=selected.symbol,
        selected_rank=selected.rank,
        ranked_count=len(ranked),
        top_n=int(top_n),
        candidates=projections,
        rejected_candidates=rejected_candidates,
        production_priority=True,
    )

