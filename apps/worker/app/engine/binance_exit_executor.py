from __future__ import annotations

from typing import Any, Callable

from apps.worker.app.engine.binance_gateway_executor import send_order_via_gateway


_FAILURE_STATUSES = {"ERROR", "TIMEOUT", "FAILED", "BLOCKED"}


def _extract_algo_id(response: dict[str, Any] | None) -> Any:
    if not isinstance(response, dict):
        return None

    data = response.get("data")
    if isinstance(data, dict):
        return data.get("algoId") or data.get("algo_id")

    return response.get("algoId") or response.get("algo_id")


def _extract_client_algo_id(order_payload: dict[str, Any]) -> Any:
    return (
        order_payload.get("clientAlgoId")
        or order_payload.get("client_algo_id")
        or order_payload.get("newClientOrderId")
    )


def _is_failed_response(response: dict[str, Any] | None) -> bool:
    if not isinstance(response, dict):
        return True

    status = str(response.get("status") or "").upper().strip()
    if status in _FAILURE_STATUSES:
        return True

    if response.get("ok") is False:
        return True

    return False


def _exit_result(order_payload: dict[str, Any], response: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "clientAlgoId": _extract_client_algo_id(order_payload),
        "algoId": _extract_algo_id(response),
    }


def create_exit_orders(
    *,
    bracket_orders: Any,
    send_order: Callable[[dict[str, Any]], dict[str, Any]] = send_order_via_gateway,
) -> dict[str, Any]:
    stop_loss_order = getattr(bracket_orders, "stop_loss_order", None)
    take_profit_order = getattr(bracket_orders, "take_profit_order", None)

    if not isinstance(stop_loss_order, dict):
        raise ValueError("stop_loss_order_required")

    if not isinstance(take_profit_order, dict):
        raise ValueError("take_profit_order_required")

    sl_response = send_order(stop_loss_order)
    sl_result = _exit_result(stop_loss_order, sl_response)

    if _is_failed_response(sl_response):
        return {
            "sl": None,
            "tp": None,
            "error": "stop_loss_failed",
        }

    tp_response = send_order(take_profit_order)
    tp_result = _exit_result(take_profit_order, tp_response)

    if _is_failed_response(tp_response):
        return {
            "sl": sl_result,
            "tp": None,
            "error": "take_profit_failed",
        }

    return {
        "sl": sl_result,
        "tp": tp_result,
    }
