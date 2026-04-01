# MODULE: execution_contract
# PURPOSE: define the internal contract for executions/fills linked to a parent order


REQUIRED_EXECUTION_FIELDS = [
    "user_id",
    "broker",
    "order_id",               # ← eje real del lifecycle
    "exec_id",
    "executed_at_precise",
    "symbol",
    "side",
    "qty",
    "price",
    "raw_status",
    "normalized_status",
]


OPTIONAL_EXECUTION_FIELDS = [
    "account",
    "broker_order_id",
    "commission",
    "currency",
    "request_id",
    "order_ref",
    "created_at",
    "updated_at",
]


VALID_NORMALIZED_EXECUTION_STATUS = [
    "filled",
    "partial_fill",
    "cancelled",
    "rejected",
    "unknown",
]


def is_valid_execution(execution: dict) -> bool:
    """
    Validate minimal structure of an execution/fill
    """
    for field in REQUIRED_EXECUTION_FIELDS:
        if field not in execution:
            return False

    if execution.get("side") not in ("BUY", "SELL"):
        return False

    try:
        float(execution.get("qty"))
        float(execution.get("price"))
    except Exception:
        return False

    if execution.get("normalized_status") not in VALID_NORMALIZED_EXECUTION_STATUS:
        return False

    return True
