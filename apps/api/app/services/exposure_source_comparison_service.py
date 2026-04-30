from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def _dec(v: Any, field: str) -> Decimal:
    try:
        return Decimal(str(v or "0"))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{field}_invalid") from None


def _norm_str(v: Any, field: str) -> str:
    s = str(v or "").strip()
    if not s:
        raise ValueError(f"{field}_required")
    return s.upper()


def compare_legacy_vs_derived_exposure(
    *,
    legacy_positions: list[dict],
    derived_positions: list[dict],
    symbol: str,
    exchange: str,
    projected_qty,
    projected_price,
) -> dict:

    sym = _norm_str(symbol, "symbol")
    exch = _norm_str(exchange, "exchange")

    p_qty = _dec(projected_qty, "projected_qty")
    p_price = _dec(projected_price, "projected_price")

    # legacy
    open_qty_legacy = Decimal("0")
    open_notional_legacy = Decimal("0")

    for p in legacy_positions:
        if not isinstance(p, dict):
            raise ValueError("legacy_row_invalid")

        if str(p.get("status", "")).upper() != "OPEN":
            continue

        if str(p.get("symbol", "")).upper() != sym:
            continue

        qty = _dec(p.get("qty"), "qty")
        price = _dec(p.get("entry_price"), "entry_price")

        open_qty_legacy += qty
        open_notional_legacy += qty * price

    # derived
    open_qty_derived = Decimal("0")
    open_notional_derived = Decimal("0")

    for d in derived_positions:
        if not isinstance(d, dict):
            raise ValueError("derived_row_invalid")

        if str(d.get("position_status", "")).upper() != "OPEN":
            continue

        if str(d.get("symbol", "")).upper() != sym:
            continue

        if str(d.get("broker", "")).upper() != exch:
            continue

        open_qty_derived += _dec(d.get("net_qty"), "net_qty")
        open_notional_derived += _dec(d.get("buy_quote_usdt"), "buy_quote_usdt")

    proj_qty_legacy = open_qty_legacy + p_qty
    proj_qty_derived = open_qty_derived + p_qty

    proj_notional_legacy = open_notional_legacy + (p_qty * p_price)
    proj_notional_derived = open_notional_derived + (p_qty * p_price)

    delta = {
        "open_qty_symbol": open_qty_legacy - open_qty_derived,
        "open_notional_exchange": open_notional_legacy - open_notional_derived,
        "projected_qty_symbol": proj_qty_legacy - proj_qty_derived,
        "projected_notional_exchange": proj_notional_legacy - proj_notional_derived,
    }

    diverged = any(v != Decimal("0") for v in delta.values())

    return {
        "symbol": sym,
        "exchange": exch,
        "legacy": {
            "open_qty_symbol": open_qty_legacy,
            "open_notional_exchange": open_notional_legacy,
            "projected_qty_symbol": proj_qty_legacy,
            "projected_notional_exchange": proj_notional_legacy,
        },
        "derived": {
            "open_qty_symbol": open_qty_derived,
            "open_notional_exchange": open_notional_derived,
            "projected_qty_symbol": proj_qty_derived,
            "projected_notional_exchange": proj_notional_derived,
        },
        "delta": delta,
        "diverged": diverged,
    }
