# MODULE: submission_result_mapper
# PURPOSE: map runtime result → internal submission result


from typing import Dict, Any


def normalize_runtime_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize runtime result payload into internal structure
    """

    success = result.get("success", False)

    base = {
        "request_id": result.get("request_id"),
        "order_id": result.get("order_id"),
        "user_id": result.get("user_id"),
        "broker": result.get("broker"),
    }

    if not success:
        return {
            **base,
            "success": False,
            "error": result.get("error"),
        }

    broker_order_id = result.get("broker_order_id")
    if not broker_order_id:
        broker_order_id = None

    return {
        **base,
        "success": True,
        "broker_order_id": broker_order_id,
        "broker_status": result.get("status"),
        "symbol": result.get("symbol"),
        "side": result.get("side"),
        "qty": result.get("qty"),
        "order_ref": result.get("order_ref"),
    }
