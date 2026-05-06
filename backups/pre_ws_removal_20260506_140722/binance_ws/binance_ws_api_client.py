import base64
import json
import time
import uuid
from typing import Any, Callable, Optional


BINANCE_WS_API_URL = "wss://ws-api.binance.com:443/ws-api/v3"


class BinanceWsApiClient:
    """
    Minimal Binance WebSocket API client for authenticated userDataStream.

    This class is intentionally transport-only:
    - No DB
    - No persistence
    - No parser
    - No execution/risk/intent integration
    - No REST trading
    - No orders
    - No infinite loop
    - No scheduler
    """

    def __init__(
        self,
        *,
        api_key: str,
        private_key: Any,
        ws_url: str = BINANCE_WS_API_URL,
        ws: Any = None,
        websocket_factory: Optional[Callable[..., Any]] = None,
        time_ms_fn: Optional[Callable[[], int]] = None,
        uuid_fn: Optional[Callable[[], str]] = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        if private_key is None:
            raise ValueError("private_key is required")

        self.api_key = api_key
        self.private_key = private_key
        self.ws_url = ws_url
        self.ws = ws
        self.websocket_factory = websocket_factory
        self.time_ms_fn = time_ms_fn or (lambda: int(time.time() * 1000))
        self.uuid_fn = uuid_fn or (lambda: str(uuid.uuid4()))
        self.timeout_seconds = 20

    def connect(self) -> None:
        if self.ws is not None:
            return

        factory = self.websocket_factory
        if factory is None:
            import websocket

            factory = websocket.create_connection

        self.ws = factory(self.ws_url, timeout=self.timeout_seconds)

        # enforce timeout at websocket level (critical to avoid blocking recv)
        try:
            if hasattr(self.ws, "settimeout"):
                self.ws.settimeout(self.timeout_seconds)
        except Exception:
            pass

        # attempt to set socket timeout as fallback
        try:
            sock = getattr(self.ws, "sock", None)
            if sock is not None and hasattr(sock, "settimeout"):
                sock.settimeout(self.timeout_seconds)
        except Exception:
            pass

    def _require_ws(self) -> Any:
        if self.ws is None:
            raise RuntimeError("WebSocket is not connected")
        return self.ws

    @staticmethod
    def _build_signature_payload(params: dict[str, Any]) -> str:
        return "&".join(
            f"{key}={params[key]}"
            for key in sorted(params)
            if key != "signature"
        )

    def _sign_ed25519_payload(self, payload: str) -> str:
        signature = self.private_key.sign(payload.encode("ASCII"))
        return base64.b64encode(signature).decode("ASCII")

    def _send_json(self, request: dict[str, Any]) -> None:
        ws = self._require_ws()
        ws.send(json.dumps(request, separators=(",", ":"), sort_keys=True))

    def session_logon(self) -> dict[str, Any]:
        self.connect()

        params = {
            "apiKey": self.api_key,
            "timestamp": self.time_ms_fn(),
        }
        payload = self._build_signature_payload(params)
        params["signature"] = self._sign_ed25519_payload(payload)

        request = {
            "id": self.uuid_fn(),
            "method": "session.logon",
            "params": params,
        }

        self._send_json(request)
        return request

    def subscribe_user_data(self) -> dict[str, Any]:
        self.connect()

        request = {
            "id": self.uuid_fn(),
            "method": "userDataStream.subscribe",
            "params": {},
        }

        self._send_json(request)
        return request

    def receive(self) -> dict[str, Any]:
        ws = self._require_ws()
        try:
            raw = ws.recv()
        except Exception as exc:
            raise RuntimeError(f"ws receive timeout or error: {exc}") from exc

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    def close(self) -> None:
        if self.ws is None:
            return

        close = getattr(self.ws, "close", None)
        if callable(close):
            close()
        self.ws = None
