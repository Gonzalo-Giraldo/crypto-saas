from __future__ import annotations

from typing import Any

from apps.api.app.services.binance_fill_reconciliation import reconcile_binance_order_fills


def _normalize_order_id(value: Any) -> str:
    order_id = str(value or "").strip()
    if not order_id:
        raise ValueError("order_id_required")
    return order_id


def _normalize_required_str(value: Any, field: str) -> str:
    out = str(value or "").strip()
    if not out:
        raise ValueError(f"{field}_required")
    return out


def _normalize_market(value: Any) -> str:
    market = str(value or "").upper().strip()
    if market not in {"SPOT", "FUTURES"}:
        raise ValueError("market_invalid")
    return market


def _trade_order_id(trade: dict[str, Any]) -> str:
    for key in ("orderId", "order_id"):
        if key in trade and trade[key] is not None:
            return str(trade[key]).strip()
    return ""


def _filter_trades_by_order_id(*, trades: list[dict[str, Any]], order_id: str) -> list[dict[str, Any]]:
    expected = _normalize_order_id(order_id)
    matched: list[dict[str, Any]] = []

    for trade in trades:
        if not isinstance(trade, dict):
            raise ValueError("trade_must_be_dict")
        got = _trade_order_id(trade)
        if got == expected:
            matched.append(trade)

    return matched


def _validate_no_mixed_order_ids(*, trades: list[dict[str, Any]], order_id: str) -> None:
    expected = _normalize_order_id(order_id)
    mixed = sorted(
        {
            _trade_order_id(trade)
            for trade in trades
            if isinstance(trade, dict) and _trade_order_id(trade) and _trade_order_id(trade) != expected
        }
    )
    if mixed:
        raise ValueError(f"mixed_order_ids_detected:{mixed}")


def run_binance_fill_ingestion_for_intent(
    *,
    db: Any,
    intent_id: str,
    symbol: str,
    order_id: Any,
    execution_ref_type: str,
    user_id: str,
    account_id: str,
    market: str,
    expected_qty: Any,
    gateway_fetch_trades,
    persist_binance_fills_db=None,
    persist: bool = False,
) -> dict[str, Any]:

    if not intent_id:
        raise ValueError("intent_id_required")

    if execution_ref_type != "orderId":
        raise ValueError("execution_ref_type_must_be_orderId")

    user_id_norm = _normalize_required_str(user_id, "user_id")
    account_id_norm = _normalize_required_str(account_id, "account_id")
    market_norm = _normalize_market(market)

    symbol_norm = str(symbol or "").upper().strip()
    if not symbol_norm:
        raise ValueError("symbol_required")

    expected_order_id = _normalize_order_id(order_id)

    if not callable(gateway_fetch_trades):
        raise ValueError("gateway_fetch_trades_callable_required")

    raw_trades = gateway_fetch_trades(symbol=symbol_norm, order_id=expected_order_id)

    if not isinstance(raw_trades, list):
        raise ValueError("gateway_trades_must_be_list")

    # mixed order ids allowed; filtering applied below

    matched_trades = _filter_trades_by_order_id(
        trades=raw_trades,
        order_id=expected_order_id,
    )

    if not matched_trades:
        return {
            "intent_id": intent_id,
            "symbol": symbol_norm,
            "order_id": expected_order_id,
            "matched_count": 0,
            "persisted": False,
            "reason": "no_matching_trades",
            "trades": [],
            "reconciliation": None,
        }

    reconciliation = reconcile_binance_order_fills(
        execution_ref=expected_order_id,
        execution_ref_type="orderId",
        expected_qty=expected_qty,
        symbol=symbol_norm,
        market=market_norm,
        fills=matched_trades,
    )

    if not isinstance(reconciliation, dict):
        raise ValueError("reconciliation_invalid")

    if reconciliation.get("safe_for_position_update") is not True:
        return {
            "intent_id": intent_id,
            "symbol": symbol_norm,
            "order_id": expected_order_id,
            "matched_count": len(matched_trades),
            "persisted": False,
            "reason": f"reconciliation_blocked:{reconciliation.get('reason')}",
            "trades": matched_trades,
            "reconciliation": reconciliation,
        }

    persisted_result = None

    if persist:
        if not callable(persist_binance_fills_db):
            raise ValueError("persist_binance_fills_db_callable_required")

        persisted_result = persist_binance_fills_db(
            db=db,
            fills=matched_trades,
            user_id=user_id_norm,
            account_id=account_id_norm,
            broker="BINANCE",
            market=market_norm,
        )

    return {
        "intent_id": intent_id,
        "symbol": symbol_norm,
        "order_id": expected_order_id,
        "matched_count": len(matched_trades),
        "persisted": bool(persist),
        "persist_result": persisted_result,
        "reason": "ok",
        "trades": matched_trades,
        "reconciliation": reconciliation,
    }
