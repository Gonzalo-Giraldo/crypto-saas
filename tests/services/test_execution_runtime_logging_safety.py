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

def test_binance_real_order_query_failure_after_send_does_not_resubmit_or_mark_executed(monkeypatch):
    import pytest
    import apps.worker.app.engine.execution_runtime as runtime

    class _DB:
        def execute(self, *args, **kwargs):
            class _Result:
                def fetchone(self):
                    return (1,)
            return _Result()

        def add(self, obj):
            return None

        def flush(self):
            return None

        def commit(self):
            return None

        def close(self):
            return None

    class _Adapter:
        def send_order(self, **kwargs):
            calls["send_order"] += 1
            return {"accepted": True}

    calls = {
        "send_order": 0,
        "mark_executed": 0,
    }

    monkeypatch.setattr(runtime, "SessionLocal", lambda: _DB())
    monkeypatch.setattr(runtime, "_assert_binance_gateway_policy", lambda: None)
    monkeypatch.setattr(
        runtime,
        "get_decrypted_exchange_secret",
        lambda db, user_id, exchange: {"api_key": "k", "api_secret": "s"},
    )
    monkeypatch.setattr(
        runtime,
        "prepare_binance_market_order_quantity",
        lambda symbol, requested_qty, market: {"normalized_qty": requested_qty},
    )
    monkeypatch.setattr(runtime, "_build_binance_client_order_id", lambda **kwargs: "cid-real-query-fail-1")
    monkeypatch.setattr(runtime, "_build_binance_broker_adapter", lambda **kwargs: _Adapter())

    def fake_query_order_status(**kwargs):
        raise RuntimeError("gateway_upstream_error status=502")

    def fake_mark_intent_executed(db, intent_key):
        calls["mark_executed"] += 1
        raise AssertionError("mark_intent_executed must not be called when order status query fails")

    monkeypatch.setattr(runtime, "query_order_status", fake_query_order_status)
    monkeypatch.setattr(runtime, "mark_intent_executed", fake_mark_intent_executed)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        runtime.execute_binance_real_order_for_user(
            user_id="user-1",
            symbol="BTCUSDT",
            side="BUY",
            qty=0.001,
            intent_key="intent-real-query-fail-1",
            account_id="default",
            market="FUTURES",
        )

    assert calls["send_order"] == 1
    assert calls["mark_executed"] == 0
    assert exc.value.status_code == 502
    assert "gateway_upstream_error status=502" in exc.value.detail
