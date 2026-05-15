from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class BinanceFuturesBracketOrders:
    entry_order: dict[str, Any]
    stop_loss_order: dict[str, Any]
    take_profit_order: dict[str, Any]


def _decimal_positive(value: Any, field: str) -> Decimal:
    try:
        out = Decimal(str(value))
    except Exception:
        raise ValueError(f"{field}_invalid") from None
    if out <= 0:
        raise ValueError(f"{field}_must_be_positive")
    return out


def _normalize_symbol(symbol: Any) -> str:
    out = str(symbol or "").upper().strip()
    if not out:
        raise ValueError("symbol_required")
    return out


def _normalize_direction(direction: Any) -> str:
    out = str(direction or "").upper().strip()
    if out not in {"LONG", "SHORT"}:
        raise ValueError("direction_must_be_LONG_or_SHORT")
    return out


def _validate_sl_tp_for_direction(
    *,
    direction: str,
    entry_price: Decimal,
    stop_loss: Decimal,
    take_profit: Decimal,
) -> None:
    if direction == "LONG":
        if not (stop_loss < entry_price < take_profit):
            raise ValueError("invalid_SL_TP_for_LONG")
        return

    if direction == "SHORT":
        if not (take_profit < entry_price < stop_loss):
            raise ValueError("invalid_SL_TP_for_SHORT")
        return

    raise ValueError("direction_must_be_LONG_or_SHORT")


def build_binance_futures_stop_loss_order(
    *,
    symbol: Any,
    direction: Any,
    qty: Any,
    stop_loss: Any,
    client_order_id: str,
) -> dict[str, Any]:
    symbol_norm = _normalize_symbol(symbol)
    direction_norm = _normalize_direction(direction)
    qty_dec = _decimal_positive(qty, "qty")
    sl_dec = _decimal_positive(stop_loss, "stop_loss")

    client_id = str(client_order_id or "").strip()
    if not client_id:
        raise ValueError("client_order_id_required")

    exit_side = "SELL" if direction_norm == "LONG" else "BUY"

    return {
        "symbol": symbol_norm,
        "market": "FUTURES",
        "side": exit_side,
        "type": "STOP_MARKET",
        "quantity": str(qty_dec),
        "stopPrice": str(sl_dec),
        "reduceOnly": True,
        "clientAlgoId": f"{client_id[:28]}-SL"[:36],
    }


def build_binance_futures_bracket_orders(
    *,
    symbol: Any,
    direction: Any,
    qty: Any,
    entry_price: Any,
    stop_loss: Any,
    take_profit: Any,
    client_order_id: str,
) -> BinanceFuturesBracketOrders:
    symbol_norm = _normalize_symbol(symbol)
    direction_norm = _normalize_direction(direction)
    qty_dec = _decimal_positive(qty, "qty")
    entry_dec = _decimal_positive(entry_price, "entry_price")
    sl_dec = _decimal_positive(stop_loss, "stop_loss")
    tp_dec = _decimal_positive(take_profit, "take_profit")

    client_id = str(client_order_id or "").strip()
    if not client_id:
        raise ValueError("client_order_id_required")

    _validate_sl_tp_for_direction(
        direction=direction_norm,
        entry_price=entry_dec,
        stop_loss=sl_dec,
        take_profit=tp_dec,
    )

    entry_side = "BUY" if direction_norm == "LONG" else "SELL"
    exit_side = "SELL" if direction_norm == "LONG" else "BUY"

    entry_order = {
        "symbol": symbol_norm,
        "market": "FUTURES",
        "side": entry_side,
        "type": "MARKET",
        "quantity": str(qty_dec),
        "newClientOrderId": client_id[:36],
    }

    stop_loss_order = build_binance_futures_stop_loss_order(
        symbol=symbol_norm,
        direction=direction_norm,
        qty=qty_dec,
        stop_loss=sl_dec,
        client_order_id=client_id,
    )

    take_profit_order = {
        "symbol": symbol_norm,
        "market": "FUTURES",
        "side": exit_side,
        "type": "TAKE_PROFIT_MARKET",
        "quantity": str(qty_dec),
        "stopPrice": str(tp_dec),
        "reduceOnly": True,
        "clientAlgoId": f"{client_id[:28]}-TP"[:36],
    }

    return BinanceFuturesBracketOrders(
        entry_order=entry_order,
        stop_loss_order=stop_loss_order,
        take_profit_order=take_profit_order,
    )
