# MODULE: order_contract
# PURPOSE: define the internal contract for an order lifecycle (multi-user, multi-broker)


REQUIRED_ORDER_FIELDS = [
    "user_id",
    "broker",
    "account",
    "order_id",        # ← núcleo real del sistema
    "request_id",      # ← origen del intent
    "symbol",
    "side",
    "qty_requested",
    "created_at",
]


OPTIONAL_ORDER_FIELDS = [
    "order_ref",
    "broker_order_id",
    "qty_filled_total",
    "lifecycle_status",
    "updated_at",
]


VALID_LIFECYCLE_STATUS = [
    "created",
    "submitted",
    "partially_filled",
    "filled",
    "cancelled",
    "rejected",
    "failed",
]


def is_valid_order(order: dict) -> bool:
    """
    Validate minimal structure of an order
    """
    for field in REQUIRED_ORDER_FIELDS:
        if field not in order:
            return False

    if order.get("side") not in ("BUY", "SELL"):
        return False

    try:
        float(order.get("qty_requested"))
    except Exception:
        return False

    return True
