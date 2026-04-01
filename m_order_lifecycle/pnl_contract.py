# MODULE: pnl_contract
# PURPOSE: define the internal contract for one PnL line per reconciled parent order


REQUIRED_PNL_FIELDS = [
    "user_id",
    "broker",
    "order_id",              # ← eje real del sistema
    "pnl_identity",
    "symbol",
    "side",
    "qty_closed",
    "avg_entry_price",
    "avg_exit_price",
    "gross_pnl",
    "total_commission",
    "net_pnl",
    "calculated_at",
]


OPTIONAL_PNL_FIELDS = [
    "account",
    "reconciliation_identity",
    "fifo_source_orders",
    "currency",
    "request_id",
    "order_ref",
    "created_at",
    "updated_at",
]


def is_valid_pnl_line(line: dict) -> bool:
    """
    Validate minimal structure of one PnL line per order
    """
    for field in REQUIRED_PNL_FIELDS:
        if field not in line:
            return False

    if line.get("side") not in ("BUY", "SELL"):
        return False

    try:
        float(line.get("qty_closed"))
        float(line.get("avg_entry_price"))
        float(line.get("avg_exit_price"))
        float(line.get("gross_pnl"))
        float(line.get("total_commission"))
        float(line.get("net_pnl"))
    except Exception:
        return False

    return True
