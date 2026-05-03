import base64
import json

import pytest

from apps.binance_ws.binance_ws_api_client import (
    BINANCE_WS_API_URL,
    BinanceWsApiClient,
)


class FakePrivateKey:
    def __init__(self):
        self.payloads = []

    def sign(self, payload: bytes) -> bytes:
        self.payloads.append(payload)
        return b"fake-signature"


class FakeWs:
    def __init__(self, recv_messages=None):
        self.sent = []
        self.closed = False
        self.recv_messages = list(recv_messages or [])

    def send(self, payload):
        self.sent.append(payload)

    def recv(self):
        if not self.recv_messages:
            raise RuntimeError("no more messages")
        return self.recv_messages.pop(0)

    def close(self):
        self.closed = True


def test_requires_api_key():
    with pytest.raises(ValueError, match="api_key is required"):
        BinanceWsApiClient(api_key="", private_key=FakePrivateKey())


def test_requires_private_key():
    with pytest.raises(ValueError, match="private_key is required"):
        BinanceWsApiClient(api_key="k", private_key=None)


def test_build_signature_payload_sorted_and_excludes_signature():
    payload = BinanceWsApiClient._build_signature_payload({
        "timestamp": 123,
        "apiKey": "abc",
        "signature": "ignore",
    })

    assert payload == "apiKey=abc&timestamp=123"


def test_session_logon_sends_signed_request_with_fake_ws():
    ws = FakeWs()
    key = FakePrivateKey()

    client = BinanceWsApiClient(
        api_key="test-key",
        private_key=key,
        ws=ws,
        time_ms_fn=lambda: 1700000000000,
        uuid_fn=lambda: "fixed-id",
    )

    request = client.session_logon()

    assert request["id"] == "fixed-id"
    assert request["method"] == "session.logon"
    assert request["params"]["apiKey"] == "test-key"
    assert request["params"]["timestamp"] == 1700000000000
    assert request["params"]["signature"] == base64.b64encode(b"fake-signature").decode("ASCII")
    assert key.payloads == [b"apiKey=test-key&timestamp=1700000000000"]

    sent = json.loads(ws.sent[0])
    assert sent == request


def test_subscribe_user_data_sends_request_with_fake_ws():
    ws = FakeWs()
    client = BinanceWsApiClient(
        api_key="test-key",
        private_key=FakePrivateKey(),
        ws=ws,
        uuid_fn=lambda: "subscribe-id",
    )

    request = client.subscribe_user_data()

    assert request == {
        "id": "subscribe-id",
        "method": "userDataStream.subscribe",
        "params": {},
    }
    assert json.loads(ws.sent[0]) == request


def test_receive_decodes_json_string():
    ws = FakeWs([
        '{"subscriptionId":0,"event":{"e":"executionReport"}}'
    ])

    client = BinanceWsApiClient(
        api_key="test-key",
        private_key=FakePrivateKey(),
        ws=ws,
    )

    assert client.receive() == {
        "subscriptionId": 0,
        "event": {"e": "executionReport"},
    }


def test_receive_decodes_json_bytes():
    ws = FakeWs([
        b'{"status":200,"result":{}}'
    ])

    client = BinanceWsApiClient(
        api_key="test-key",
        private_key=FakePrivateKey(),
        ws=ws,
    )

    assert client.receive() == {
        "status": 200,
        "result": {},
    }


def test_receive_requires_connection():
    client = BinanceWsApiClient(
        api_key="test-key",
        private_key=FakePrivateKey(),
    )

    with pytest.raises(RuntimeError, match="WebSocket is not connected"):
        client.receive()


def test_connect_uses_injected_factory():
    created = []

    def factory(url, timeout):
        created.append((url, timeout))
        return FakeWs()

    client = BinanceWsApiClient(
        api_key="test-key",
        private_key=FakePrivateKey(),
        websocket_factory=factory,
    )

    client.connect()

    assert created == [(BINANCE_WS_API_URL, 20)]
    assert isinstance(client.ws, FakeWs)


def test_connect_does_not_replace_existing_ws():
    ws = FakeWs()

    def factory(url, timeout):
        raise AssertionError("factory must not be called")

    client = BinanceWsApiClient(
        api_key="test-key",
        private_key=FakePrivateKey(),
        ws=ws,
        websocket_factory=factory,
    )

    client.connect()

    assert client.ws is ws


def test_close_closes_ws_and_clears_reference():
    ws = FakeWs()
    client = BinanceWsApiClient(
        api_key="test-key",
        private_key=FakePrivateKey(),
        ws=ws,
    )

    client.close()

    assert ws.closed is True
    assert client.ws is None


def test_module_has_no_forbidden_runtime_dependencies():
    import pathlib

    source = pathlib.Path("apps/binance_ws/binance_ws_api_client.py").read_text()

    forbidden = [
        "sqlalchemy",
        "create_engine",
        "sessionmaker",
        "persist_binance_fills_db",
        "parse_execution_report_event",
        "requests.",
        "client.order",
        "create_order",
        "cancel_order",
        "ops.py",
    ]

    for token in forbidden:
        assert token not in source
