from __future__ import annotations

from typing import Any


def evaluate_binance_autopick_market_context(
    *,
    ticker_rows: list[dict[str, Any]],
    klines_1h_by_symbol: dict[str, list[list[Any]]],
    klines_15m_by_symbol: dict[str, list[list[Any]]],
    top_n: int = 10,
    max_symbols: int | None = None,
):
    raise NotImplementedError("evaluation_engine_not_wired")
