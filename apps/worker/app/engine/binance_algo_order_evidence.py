from __future__ import annotations

from typing import Any


def extract_algo_order_evidence(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "has_payload": False,
            "status": None,
            "has_status": False,
            "algo_id": None,
            "has_algo_id": False,
            "client_algo_id": None,
            "has_client_algo_id": False,
            "executed_qty": None,
            "has_executed_qty": False,
            "raw_payload_type": type(payload).__name__,
            "protection_active_declared": False,
        }

    status = payload.get("status")
    algo_id = payload.get("algoId") or payload.get("algo_id")
    client_algo_id = (
        payload.get("clientAlgoId")
        or payload.get("client_algo_id")
        or payload.get("clientOrderId")
    )
    executed_qty = (
        payload.get("executedQty")
        or payload.get("cumQty")
        or payload.get("cumBase")
    )

    return {
        "has_payload": True,
        "status": str(status).upper().strip() if status is not None else None,
        "has_status": bool(str(status or "").strip()),
        "algo_id": algo_id,
        "has_algo_id": algo_id is not None,
        "client_algo_id": client_algo_id,
        "has_client_algo_id": bool(str(client_algo_id or "").strip()),
        "executed_qty": executed_qty,
        "has_executed_qty": executed_qty is not None,
        "raw_payload_type": "dict",
        "protection_active_declared": False,
    }
