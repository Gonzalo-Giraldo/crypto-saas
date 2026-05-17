from __future__ import annotations

from typing import Any

from apps.api.app.services.auto_pick.binance.observation_contracts import (
    BinanceMarketObservationSnapshot,
)
from apps.api.app.services.auto_pick.binance.evaluation_engine import (
    evaluate_binance_autopick_market_context,
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

    return evaluate_binance_autopick_market_context(
        ticker_rows=context["ticker_rows"],
        klines_1h_by_symbol=context["klines_1h"],
        klines_15m_by_symbol=context["klines_15m"],
        top_n=top_n,
        max_symbols=max_symbols,
    )

