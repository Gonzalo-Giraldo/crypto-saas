import json
from typing import Any

from apps.binance_ws.run_real_ws_controlled_session_dry_run import (
    build_real_ws_client_from_env,
)
from apps.binance_ws_worker.config import BinanceWsWorkerConfig


def _safe_event_payload(message: dict[str, Any]) -> dict[str, Any]:
    event = message.get("event")
    if not isinstance(event, dict):
        return {
            "kind": "non_event_message",
            "keys": sorted(message.keys()),
            "status": message.get("status"),
            "id": message.get("id"),
        }

    return {
        "kind": "event",
        "event_type": event.get("e"),
        "execution_type": event.get("x"),
        "symbol": event.get("s"),
        "order_id": event.get("i"),
        "trade_id": event.get("t"),
        "side": event.get("S"),
        "order_type": event.get("o"),
        "last_executed_qty": event.get("l"),
        "last_executed_price": event.get("L"),
        "event_time": event.get("E"),
    }


def build_worker_status(config: BinanceWsWorkerConfig | None = None) -> dict[str, Any]:
    cfg = config or BinanceWsWorkerConfig()
    cfg.validate()

    return {
        "worker_name": cfg.worker_name,
        "mode": cfg.mode,
        "safe_to_run": cfg.mode == "dry-run",
        "live_enabled": cfg.live_enabled,
        "network_enabled": False,
        "db_writes_enabled": False,
        "orders_enabled": False,
    }


def run_ws_dry_loop(max_events: int = 5) -> dict[str, Any]:
    if max_events is None or max_events <= 0:
        raise ValueError("max_events must be > 0")

    client = build_real_ws_client_from_env()
    received: list[dict[str, Any]] = []
    errors: list[str] = []

    try:
        client.connect()

        logon_request = client.session_logon()
        print("WS_WORKER_LOGON_REQUEST_SAFE")
        print(json.dumps({
            "id": logon_request.get("id"),
            "method": logon_request.get("method"),
            "params_keys": sorted((logon_request.get("params") or {}).keys()),
            "redacted": ["apiKey", "signature"],
        }, indent=2, sort_keys=True))

        logon_response = client.receive()
        print("WS_WORKER_LOGON_RESPONSE_SAFE")
        print(json.dumps(_safe_event_payload(logon_response), indent=2, sort_keys=True))

        subscribe_request = client.subscribe_user_data()
        print("WS_WORKER_SUBSCRIBE_REQUEST_SAFE")
        print(json.dumps({
            "id": subscribe_request.get("id"),
            "method": subscribe_request.get("method"),
            "params_keys": sorted((subscribe_request.get("params") or {}).keys()),
        }, indent=2, sort_keys=True))

        subscribe_response = client.receive()
        print("WS_WORKER_SUBSCRIBE_RESPONSE_SAFE")
        print(json.dumps(_safe_event_payload(subscribe_response), indent=2, sort_keys=True))

        for _ in range(max_events):
            message = client.receive()
            safe_message = _safe_event_payload(message)
            received.append(safe_message)
            print("WS_WORKER_EVENT_SAFE")
            print(json.dumps(safe_message, indent=2, sort_keys=True))

    except Exception as exc:
        errors.append(str(exc))
        print("WS_WORKER_ERROR")
        print(str(exc))
    finally:
        client.close()
        print("WS_WORKER_CLOSED")

    return {
        "worker_name": "binance_ws_worker",
        "mode": "dry-run",
        "received": len(received),
        "errors": errors,
        "closed": True,
    }


def main(
    config: BinanceWsWorkerConfig | None = None,
    *,
    execute_ws: bool = False,
    max_events: int = 5,
) -> dict[str, Any]:
    status = build_worker_status(config)
    print("BINANCE_WS_WORKER_STATUS")
    print(json.dumps(status, indent=2, sort_keys=True))

    if status["mode"] == "dry-run" and execute_ws:
        ws_result = run_ws_dry_loop(max_events=max_events)
        status["ws_result"] = ws_result

    return status


if __name__ == "__main__":
    main()
