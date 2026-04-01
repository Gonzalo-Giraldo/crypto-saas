# MODULE: reconciliation_contract
# PURPOSE: define the internal contract for one reconciliation line per parent order


REQUIRED_RECONCILIATION_FIELDS = [
    "user_id",
    "broker",
    "order_id",                   # ← eje real del sistema
    "reconciliation_identity",
    "symbol",
    "side",
    "qty_requested",
    "qty_executed_total",
    "avg_execution_price",
    "reconciliation_status",
    "reconciled_at",
]


OPTIONAL_RECONCILIATION_FIELDS = [
    "account",
    "broker_order_id",
    "fill_count",
    "total_commission",
    "reconciliation_reason",
    "request_id",
    "order_ref",
    "created_at",
    "updated_at",
]


VALID_RECONCILIATION_STATUS = [
    "pending",
    "partial",
    "reconciled",
    "overfilled",
    "underfilled",
    "failed",
]


def is_valid_reconciliation_line(line: dict) -> bool:
    """
    Validate minimal structure of one reconciliation line per order
    """
    for field in REQUIRED_RECONCILIATION_FIELDS:
        if field not in line:
            return False

    if line.get("side") not in ("BUY", "SELL"):
        return False

    try:
        float(line.get("qty_requested"))
        float(line.get("qty_executed_total"))
        float(line.get("avg_execution_price"))
    except Exception:
        return False

    if line.get("reconciliation_status") not in VALID_RECONCILIATION_STATUS:
        return False

    return True
