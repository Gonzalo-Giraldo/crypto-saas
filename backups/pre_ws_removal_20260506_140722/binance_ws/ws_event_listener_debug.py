import json
import os
import time

from apps.binance_ws.run_real_ws_controlled_session_dry_run import build_real_ws_client_from_env


def _safe_print_response(label, raw):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    data = json.loads(raw)
    result = data.get("result")
    if isinstance(result, dict) and "apiKey" in result:
        result = dict(result)
        result["apiKey"] = "<REDACTED>"
        data["result"] = result
    print(label)
    print(json.dumps(data, indent=2, sort_keys=True))


def main():
    max_events = int(os.environ.get("BINANCE_WS_LISTENER_MAX_EVENTS", "20"))
    idle_sleep = float(os.environ.get("BINANCE_WS_LISTENER_IDLE_SLEEP", "0.2"))

    client = build_real_ws_client_from_env()
    client.connect()

    try:
        print("WS_EVENT_LISTENER_START")

        client.session_logon()
        logon_raw = client.ws.recv()
        _safe_print_response("LOGON_RESPONSE_SAFE", logon_raw)

        client.subscribe_user_data()
        subscribe_raw = client.ws.recv()
        _safe_print_response("SUBSCRIBE_RESPONSE_SAFE", subscribe_raw)

        print("WS_EVENT_LISTENER_READY")
        print("NOW_PLACE_ONE_MANUAL_BINANCE_UI_ORDER")

        received = 0
        while received < max_events:
            try:
                raw = client.ws.recv()
            except Exception as exc:
                print("RECV_ERROR")
                print(repr(exc))
                time.sleep(idle_sleep)
                continue

            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")

            print("EVENT:")
            print(raw)
            received += 1

        print("WS_EVENT_LISTENER_DONE")

    finally:
        client.close()
        print("WS_EVENT_LISTENER_CLOSED")


if __name__ == "__main__":
    main()
