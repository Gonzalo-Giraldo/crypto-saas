from apps.worker.app.engine.binance_gateway_executor import sanitize_order_payload


def test_sanitize_removes_secrets():
    payload = {
        "symbol": "BTCUSDT",
        "api_key": "123",
        "signature": "abc",
    }

    safe = sanitize_order_payload(payload)

    assert safe["api_key"] == "[REDACTED]"
    assert safe["signature"] == "[REDACTED]"
    assert safe["symbol"] == "BTCUSDT"
