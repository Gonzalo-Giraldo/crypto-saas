from __future__ import annotations

from typing import Any


_DEFAULT_MIN_QUOTE_VOLUME = 1_000_000.0


def _to_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


def _symbol_from_row(row: dict[str, Any]) -> str:
    return str(row.get("symbol") or "").upper().strip()


def build_candidate_symbols(
    ticker_rows: list[dict[str, Any]],
    *,
    min_quote_volume: float = _DEFAULT_MIN_QUOTE_VOLUME,
) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()

    min_volume = _to_float(min_quote_volume)
    if min_volume is None or min_volume < 0:
        return []

    for row in ticker_rows:
        if not isinstance(row, dict):
            continue

        symbol = _symbol_from_row(row)
        if not symbol.endswith("USDT"):
            continue

        last_price = _to_float(row.get("lastPrice"))
        if last_price is None or last_price <= 0:
            continue

        quote_volume = _to_float(row.get("quoteVolume"))
        if quote_volume is None or quote_volume < min_volume:
            continue

        if symbol in seen:
            continue

        seen.add(symbol)
        symbols.append(symbol)

    return symbols
