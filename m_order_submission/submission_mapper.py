# MODULE: submission_mapper
# PURPOSE: map submission_contract → runtime command payload


from typing import Dict, Any
from m_order_submission.submission_contract import is_valid_submission


def build_runtime_command(submission: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert internal submission into runtime command payload
    """

    if not is_valid_submission(submission):
        raise ValueError("invalid_submission_contract")

    user_id = submission["user_id"]
    broker = submission["broker"]
    request_id = submission["request_id"]
    order_id = submission["order_id"]

    symbol = submission["symbol"]
    side = submission["side"]
    qty = float(submission["qty"])

    order_ref = submission.get("order_ref") or str(order_id)

    command = {
        "request_id": request_id,
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "order_ref": order_ref,

        # 🔴 NUEVO (clave para lifecycle)
        "user_id": user_id,
        "order_id": order_id,
        "broker": broker,
    }

    return command
