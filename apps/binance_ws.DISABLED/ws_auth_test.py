import base64
import json
import os
import time
import uuid

from cryptography.hazmat.primitives.serialization import load_pem_private_key


WS_URL = "wss://ws-api.binance.com/ws-api/v3"


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value or not value.strip():
        raise RuntimeError(f"Missing required env var: {name}")
    return value.strip()


def _load_private_key_from_env():
    raw = _require_env("BINANCE_WS_ED25519_PRIVATE_KEY")
    pem = raw.replace("\\n", "\n").encode("utf-8")
    return load_pem_private_key(data=pem, password=None)


def _build_signature_payload(params: dict) -> str:
    ordered = dict(sorted(params.items()))
    return "&".join(f"{key}={value}" for key, value in ordered.items())


def _sign_ed25519_payload(private_key, payload: str) -> str:
    signature = private_key.sign(payload.encode("utf-8"))
    return base64.b64encode(signature).decode("ascii")


def build_session_logon_request() -> dict:
    api_key = _require_env("BINANCE_WS_API_KEY")
    private_key = _load_private_key_from_env()

    params = {
        "apiKey": api_key,
        "timestamp": int(time.time() * 1000),
    }

    payload = _build_signature_payload(params)
    params["signature"] = _sign_ed25519_payload(private_key, payload)

    return {
        "id": str(uuid.uuid4()),
        "method": "session.logon",
        "params": params,
    }


def main() -> None:
    request = build_session_logon_request()

    try:
        import websocket
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency websocket-client. Install it only in the isolated runtime if needed."
        ) from exc

    print("BINANCE_WS_AUTH_TEST_START")
    print(f"ws_url={WS_URL}")
    print("request_method=session.logon")
    print("request_contains_api_key=true")
    print("request_contains_signature=true")
    print("request_payload_secret_values_printed=false")

    ws = websocket.create_connection(WS_URL, timeout=20)
    try:
        ws.send(json.dumps(request))
        response = ws.recv()
        print("BINANCE_WS_AUTH_TEST_RESPONSE_BEGIN")
        print(response)
        print("BINANCE_WS_AUTH_TEST_RESPONSE_END")
    finally:
        ws.close()
        print("BINANCE_WS_AUTH_TEST_CLOSED")


if __name__ == "__main__":
    main()
