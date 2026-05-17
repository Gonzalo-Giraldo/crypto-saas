from __future__ import annotations

from typing import Any

from apps.api.app.services.auto_pick.binance.observation_contracts import (
    BinanceMarketObservationSnapshot,
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
