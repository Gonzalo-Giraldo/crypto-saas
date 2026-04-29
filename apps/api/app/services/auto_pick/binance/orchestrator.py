from __future__ import annotations

from typing import Any, List

from apps.api.app.services.auto_pick.contracts import (
    AutoPickDecision,
    AutoPickNoTrade,
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


def run_binance_auto_pick() -> AutoPickResult:
    try:
        ticker_rows = fetch_ticker_24h_rows()
        if not ticker_rows:
            return AutoPickNoTrade(broker="BINANCE", reason="no_ticker_data")

        symbols = build_candidate_symbols(ticker_rows)
        if not symbols:
            return AutoPickNoTrade(broker="BINANCE", reason="no_symbols")

        evaluations: List[dict[str, Any]] = []

        for symbol in symbols:
            ticker = next((r for r in ticker_rows if r.get("symbol") == symbol), None)
            if not ticker:
                continue

            klines_1h = fetch_1h_klines(symbol)
            klines_15m = fetch_15m_klines(symbol)

            if not klines_1h or not klines_15m:
                continue

            try:
                candidate = build_crypto_model_input(
                    symbol=symbol,
                    klines_1h=klines_1h,
                    klines_15m=klines_15m,
                    ticker_24h=ticker,
                )
            except Exception:
                continue

            evaluation = compute_final_score(candidate)

            if evaluation.get("valid"):
                side = str(evaluation.get("side") or "").upper().strip()
                if side not in {"BUY", "SELL"}:
                    continue
                evaluation["side"] = side
                evaluations.append(evaluation)

        if not evaluations:
            return AutoPickNoTrade(broker="BINANCE", reason="no_valid_candidates")

        ranked = sorted(evaluations, key=lambda x: x.get("final_score", 0), reverse=True)
        top = ranked[0]

        side = str(top.get("side") or "").upper().strip()
        if side not in {"BUY", "SELL"}:
            return AutoPickNoTrade(
                broker="BINANCE",
                reason="side_invalid",
                evidence={"selected": top},
            )

        direction = "LONG" if side == "BUY" else "SHORT"

        return AutoPickDecision(
            symbol=top.get("symbol"),
            side=side,
            direction=direction,
            broker="BINANCE",
            asset_profile="CRYPTO",
            model_version="binance_auto_pick_pipeline_v1",
            final_score=float(top.get("final_score", 0)),
            decision_reason="selected_top_ranked_candidate",
            evidence={
                "ranked_count": len(evaluations),
                "selected_rank": 1,
            },
        )

    except Exception:
        return AutoPickNoTrade(broker="BINANCE", reason="orchestrator_failure")
