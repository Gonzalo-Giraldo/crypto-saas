import time

import pytest
from fastapi import HTTPException

from apps.binance_gateway import main


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def reset_circuit():
    with main._CIRCUIT_LOCK:
        main._circuit_state["fail_count"] = 0
        main._circuit_state["open_until"] = 0.0


def test_binance_418_opens_circuit_immediately():
    reset_circuit()

    response = FakeResponse(
        418,
        {"code": -1003, "msg": "Way too many requests; IP banned until 1778420458716."},
    )

    with pytest.raises(HTTPException) as exc:
        main._raise_upstream_http_error(response)

    assert exc.value.status_code == 503
    assert exc.value.detail == "binance_ip_banned_or_rate_limited"

    with main._CIRCUIT_LOCK:
        assert main._circuit_state["fail_count"] == main.CIRCUIT_BREAKER_THRESHOLD
        assert main._circuit_state["open_until"] > time.time()


def test_binance_minus_1003_opens_circuit_immediately():
    reset_circuit()

    response = FakeResponse(
        429,
        {"code": -1003, "msg": "Too many requests."},
    )

    with pytest.raises(HTTPException) as exc:
        main._raise_upstream_http_error(response)

    assert exc.value.status_code == 503
    assert exc.value.detail == "binance_ip_banned_or_rate_limited"

    with main._CIRCUIT_LOCK:
        assert main._circuit_state["fail_count"] == main.CIRCUIT_BREAKER_THRESHOLD
        assert main._circuit_state["open_until"] > time.time()


def test_open_circuit_blocks_before_upstream(monkeypatch):
    reset_circuit()

    called = {"value": False}

    def fake_raw(*args, **kwargs):
        called["value"] = True
        return FakeResponse(200, {"ok": True})

    monkeypatch.setattr(main, "_request_upstream_raw", fake_raw)

    with main._CIRCUIT_LOCK:
        main._circuit_state["open_until"] = time.time() + 60

    with pytest.raises(HTTPException) as exc:
        main._request_upstream("GET", "https://fapi.binance.com/fapi/v1/time", timeout=1)

    assert exc.value.status_code == 503
    assert exc.value.detail == "binance_circuit_open"
    assert called["value"] is False
