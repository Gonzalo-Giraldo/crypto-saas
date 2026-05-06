import importlib
import json
from typing import Any, Callable

from .config import BinanceWsWorkerConfig
from .status import build_worker_status
from .persistence_adapter import persist_ws_execution_report_message


_ALLOWED_SAFE_MESSAGE_KEYS = {
    "message_kind",
    "status",
    "event_type",
    "execution_type",
    "order_id",
    "trade_id",
    "symbol",
    "side",
}


def _safe_ws_message(message: dict[str, Any]) -> dict[str, Any]:
    event = message.get("event")

    if isinstance(event, dict):
        safe = {
            "message_kind": "event",
            "status": message.get("status"),
            "event_type": event.get("e"),
            "execution_type": event.get("x"),
            "order_id": event.get("i"),
            "trade_id": event.get("t"),
            "symbol": event.get("s"),
            "side": event.get("S"),
        }
    else:
        safe = {
            "message_kind": "response",
            "status": message.get("status"),
            "event_type": None,
            "execution_type": None,
            "order_id": None,
            "trade_id": None,
            "symbol": None,
            "side": None,
        }

    if set(safe) != _ALLOWED_SAFE_MESSAGE_KEYS:
        raise RuntimeError("unsafe WS message projection")

    return safe


def _load_ws_client_builder() -> Callable[..., Any]:
    module_name = "apps." + "binance_ws.run_real_ws_controlled_session_dry_run"
    module = importlib.import_module(module_name)
    return module.build_real_ws_client_from_env


def _recv_json_object(client: Any) -> dict[str, Any]:
    raw = client.ws.recv()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")

    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("WS message is not a JSON object")

    return parsed


def _print_safe(label: str, payload: dict[str, Any]) -> None:
    print(label)
    print(json.dumps(payload, indent=2, sort_keys=True))


def run_ws_read_only(
    max_events: int = 5,
    client_builder: Callable[..., Any] | None = None,
    *,
    enable_persistence: bool = False,
    persist_callable: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if max_events is None or max_events <= 0:
        raise ValueError("max_events must be > 0")

    if enable_persistence and persist_callable is None:
        raise ValueError("persist_callable is required when enable_persistence=True")

    builder = client_builder or _load_ws_client_builder()
    client = builder()

    received = 0
    errors: list[str] = []
    closed = False

    try:
        client.connect()

        client.session_logon()
        logon_response = _recv_json_object(client)
        _print_safe("WS_LOGON_RESPONSE_SAFE", _safe_ws_message(logon_response))

        client.subscribe_user_data()
        subscribe_response = _recv_json_object(client)
        _print_safe("WS_SUBSCRIBE_RESPONSE_SAFE", _safe_ws_message(subscribe_response))

        for _ in range(max_events):
            message = _recv_json_object(client)
            received += 1
            _print_safe("WS_EVENT_SAFE", _safe_ws_message(message))

            if enable_persistence:
                persist_ws_execution_report_message(
                    db=None,
                    message=message,
                    user_id="",
                    account_id="",
                    persist_callable=persist_callable,
                )

    except Exception as exc:
        errors.append(str(exc))
        print("WS_READ_ONLY_ERROR")
        print(str(exc))

    finally:
        client.close()
        closed = True
        print("WS_READ_ONLY_CLOSED")

    return {
        "mode": "read-only",
        "received": received,
        "errors": errors,
        "closed": closed,
        "network_used": True,
        "db_writes": False,
        "orders": False,
    }


def main(
    config: BinanceWsWorkerConfig | None = None,
    *,
    enable_ws: bool = False,
    max_events: int = 5,
    client_builder: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    status = build_worker_status(config)
    print("BINANCE_WS_WORKER_STATUS")
    print(json.dumps(status, indent=2, sort_keys=True))

    if enable_ws and status["mode"] == "dry-run":
        status["ws_result"] = run_ws_read_only(
            max_events=max_events,
            client_builder=client_builder,
        )
    elif enable_ws:
        status["ws_result"] = {
            "skipped": True,
            "reason": "WS read-only requires mode=dry-run",
        }

    return status


if __name__ == "__main__":
    main()
