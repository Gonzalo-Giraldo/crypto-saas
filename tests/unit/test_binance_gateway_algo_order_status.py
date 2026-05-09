from fastapi.testclient import TestClient

from apps.binance_gateway.main import app


client = TestClient(app)


def _headers():
    return {
        "x-internal-token": "test-token",
    }


def _payload_base():
    return {
        "api_key": "key",
        "api_secret": "secret",
        "symbol": "BTCUSDT",
    }


def test_algo_order_status_rejects_without_identifiers(monkeypatch):
    from apps.binance_gateway import main

    monkeypatch.setattr(main, "INTERNAL_TOKEN", "test-token")

    response = client.post(
        "/binance/algo-order-status",
        json=_payload_base(),
        headers=_headers(),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "exactly_one_algo_identifier_required"


def test_algo_order_status_rejects_both_identifiers(monkeypatch):
    from apps.binance_gateway import main

    monkeypatch.setattr(main, "INTERNAL_TOKEN", "test-token")

    payload = _payload_base()
    payload["algoId"] = 123
    payload["clientAlgoId"] = "abc"

    response = client.post(
        "/binance/algo-order-status",
        json=payload,
        headers=_headers(),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "exactly_one_algo_identifier_required"


def test_algo_order_status_accepts_client_algo_id(monkeypatch):
    from apps.binance_gateway import main

    monkeypatch.setattr(main, "INTERNAL_TOKEN", "test-token")

    captured = {}

    class DummyResponse:
        status_code = 200

        def json(self):
            return {"status": "NEW"}

    def fake_request(method, url, headers=None, timeout=None):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return DummyResponse()

    monkeypatch.setattr(main, "_request_upstream", fake_request)

    payload = _payload_base()
    payload["clientAlgoId"] = "client-123"

    response = client.post(
        "/binance/algo-order-status",
        json=payload,
        headers=_headers(),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["ok"] is True
    assert body["mode"] == "gateway_algo_order_status_futures"

    assert captured["method"] == "GET"
    assert "/fapi/v1/algoOrder" in captured["url"]
    assert "clientAlgoId=client-123" in captured["url"]

    assert captured["headers"]["X-MBX-APIKEY"] == "key"

    assert "DELETE" not in captured["method"]
    assert "POST" not in captured["method"]


def test_algo_order_status_accepts_algo_id(monkeypatch):
    from apps.binance_gateway import main

    monkeypatch.setattr(main, "INTERNAL_TOKEN", "test-token")

    captured = {}

    class DummyResponse:
        status_code = 200

        def json(self):
            return {"status": "NEW"}

    def fake_request(method, url, headers=None, timeout=None):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        return DummyResponse()

    monkeypatch.setattr(main, "_request_upstream", fake_request)

    payload = _payload_base()
    payload["algoId"] = 999

    response = client.post(
        "/binance/algo-order-status",
        json=payload,
        headers=_headers(),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["mode"] == "gateway_algo_order_status_futures"

    assert captured["method"] == "GET"
    assert "/fapi/v1/algoOrder" in captured["url"]
    assert "algoId=999" in captured["url"]

    assert captured["headers"]["X-MBX-APIKEY"] == "key"
