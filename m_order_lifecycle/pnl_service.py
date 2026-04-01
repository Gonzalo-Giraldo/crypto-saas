# MODULE: pnl_service
# PURPOSE: orchestrate FIFO PnL calculation per order_id using execution fills

from typing import List, Dict, Any
from apps.api.app.services.pnl_fifo import calculate_fifo_pnl


def _to_fifo_fill(execution: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "fill_id": execution["exec_id"],
        "qty": float(execution["qty"]),
        "price": float(execution["price"]),
        "timestamp": execution["executed_at_precise"],
        "commission_value_base": execution.get("commission"),
    }


def build_pnl_for_order(
    order: Dict[str, Any],
    executions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build PnL line for one SELL order_id using FIFO
    """

    user_id = order["user_id"]
    broker = order["broker"]
    order_id = order["order_id"]
    symbol = order["symbol"]
    side = order["side"]

    if side != "SELL":
        return {
            "user_id": user_id,
            "broker": broker,
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "gross_pnl": 0.0,
            "total_commission": 0.0,
            "net_pnl": 0.0,
            "fifo_matches": [],
            "complete": True,
            "reason": "pnl_only_applies_to_closing_sell_orders",
        }

    relevant_execs = [
        e for e in executions
        if e["user_id"] == user_id
        and e["broker"] == broker
        and e["symbol"] == symbol
        and float(e.get("qty", 0)) > 0
    ]

    target_sell_execs = [
        e for e in relevant_execs
        if e["order_id"] == order_id and e["side"] == "SELL"
    ]

    if not target_sell_execs:
        return {
            "user_id": user_id,
            "broker": broker,
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "gross_pnl": 0.0,
            "total_commission": 0.0,
            "net_pnl": 0.0,
            "fifo_matches": [],
            "complete": False,
            "reason": "no_sell_executions_for_order",
        }

    sell_cutoff = max(e["executed_at_precise"] for e in target_sell_execs)

    candidate_buy_execs = [
        e for e in relevant_execs
        if e["side"] == "BUY"
        and e["executed_at_precise"] <= sell_cutoff
    ]

    buy_fills = [_to_fifo_fill(e) for e in candidate_buy_execs]
    sell_fills = [_to_fifo_fill(e) for e in target_sell_execs]

    fifo_result = calculate_fifo_pnl(buy_fills, sell_fills)

    fifo_source_orders = sorted({
        e["order_id"]
        for e in candidate_buy_execs
        if e["exec_id"] in {
            m["buy_fill_id"] for m in fifo_result["matches"] if m.get("buy_fill_id")
        }
    })

    pnl_line = {
        "user_id": user_id,
        "broker": broker,
        "order_id": order_id,
        "symbol": symbol,
        "side": side,
        "gross_pnl": fifo_result["gross_pnl"],
        "total_commission": fifo_result["total_commission_base"],
        "net_pnl": fifo_result["net_pnl"],
        "fifo_source_orders": fifo_source_orders,
        "fifo_matches": fifo_result["matches"],
        "complete": fifo_result["complete"],
    }

    return pnl_line
