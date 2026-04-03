# MODULE: reconciliation_service
# PURPOSE: build one reconciliation line per order_id from executions

from typing import List, Dict, Any


def build_reconciliation_for_order(
    order: Dict[str, Any],
    executions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build reconciliation line for one order_id
    """

    user_id = order["user_id"]
    broker = order["broker"]
    order_id = order["order_id"]
    symbol = order["symbol"]
    side = order["side"]
    qty_requested = float(order["qty_requested"])

    # 🔴 executions de esta orden
    order_execs = [
        e for e in executions
        if e["user_id"] == user_id
        and e["broker"] == broker
        and e["order_id"] == order_id
        and float(e.get("qty", 0)) >= 0  # incluye qty=0 (errores)
    ]

    # 🔴 solo fills reales
    fill_execs = [
        e for e in order_execs
        if float(e.get("qty", 0)) > 0
    ]

    qty_executed = sum(float(e["qty"]) for e in fill_execs)

    if qty_executed > 0:
        avg_price = sum(
            float(e["qty"]) * float(e["price"])
            for e in fill_execs
        ) / qty_executed
    else:
        avg_price = 0.0

    total_commission = sum(
        float(e.get("commission") or 0.0)
        for e in fill_execs
    )

    fill_count = len(fill_execs)

    # 🔴 estado
    if not order_execs:
        status = "pending"
    elif qty_executed == 0:
        status = "failed"
    elif qty_executed < qty_requested:
        status = "partial"
    elif qty_executed == qty_requested:
        status = "reconciled"
    elif qty_executed > qty_requested:
        status = "overfilled"
    else:
        status = "unknown"

    reconciliation_line = {
        "user_id": user_id,
        "broker": broker,
        "order_id": order_id,
        "symbol": symbol,
        "side": side,
        "qty_requested": qty_requested,
        "qty_executed_total": qty_executed,
        "avg_execution_price": avg_price,
        "total_commission": total_commission,
        "fill_count": fill_count,
        "reconciliation_status": status,
    }

    return reconciliation_line
