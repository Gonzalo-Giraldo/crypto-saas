from __future__ import annotations

import pytest
import requests

from apps.worker.app.engine.binance_gateway_executor import (
    fetch_algo_order_status_via_gateway,
    sanitize_order_payload,
    send_order_via_gateway,
    validate_futures_order_payload,
)

class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


def test_validate_market_order_futures_only():
    out = validate_futures_order_payload(
        {
            "symbol": "btcusdt",
            "market": "FUTURES",
            "side": "buy",
            "type": "market",
            "quantity": "0.01",
        }
    )

    assert out["symbol"] == "BTCUSDT"
    assert out["market"] == "FUTURES"
    assert out["side"] == "BUY"
    assert out["type"] == "MARKET"


def test_rejects_spot_payload():
    with pytest.raises(ValueError, match="market_must_be_FUTURES"):
        validate_futures_order_payload(
            {
                "symbol": "BTCUSDT",
                "market": "SPOT",
                "side": "BUY",
                "type": "MARKET",
                "quantity": "0.01",
            }
        )


def test_stop_market_requires_reduce_only_and_stop_price():
    with pytest.raises(ValueError, match="stopPrice_required_for_trigger_order"):
        validate_futures_order_payload(
            {
                "symbol": "BTCUSDT",
                "market": "FUTURES",
                "side": "SELL",
                "type": "STOP_MARKET",
                "quantity": "0.01",
                "reduceOnly": True,
            }
        )

    with pytest.raises(ValueError, match="reduceOnly_true_required_for_exit_order"):
        validate_futures_order_payload(
            {
                "symbol": "BTCUSDT",
                "market": "FUTURES",
                "side": "SELL",
                "type": "STOP_MARKET",
                "quantity": "0.01",
                "stopPrice": "90000",
                "reduceOnly": False,
            }
        )


def test_take_profit_market_requires_reduce_only_and_stop_price():
    out = validate_futures_order_payload(
        {
            "symbol": "BTCUSDT",
            "market": "FUTURES",
            "side": "SELL",
            "type": "TAKE_PROFIT_MARKET",
            "quantity": "0.01",
            "stopPrice": "120000",
            "reduceOnly": True,
        }
    )

    assert out["type"] == "TAKE_PROFIT_MARKET"
    assert out["reduceOnly"] is True


def test_send_order_uses_configured_gateway_and_keeps_payload():
    calls = []

    def fake_post(url, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse({"ok": True, "data": {"orderId": 123}})

    result = send_order_via_gateway(
        {
            "symbol": "BTCUSDT",
            "market": "FUTURES",
            "side": "BUY",
            "type": "MARKET",
            "quantity": "0.01",
        },
        post=fake_post,
    )

    assert result["ok"] is True
    assert calls[0]["url"].endswith("/binance/order")
    assert calls[0]["json"]["market"] == "FUTURES"
    assert calls[0]["json"]["type"] == "MARKET"


def test_sanitize_order_payload_redacts_sensitive_fields():
    safe = sanitize_order_payload(
        {
            "api_key": "k",
            "api_secret": "s",
            "signature": "sig",
            "DATABASE_URL": "db",
            "symbol": "BTCUSDT",
        }
    )

    assert safe["api_key"] == "[REDACTED]"
    assert safe["api_secret"] == "[REDACTED]"
    assert safe["signature"] == "[REDACTED]"
    assert safe["DATABASE_URL"] == "[REDACTED]"
    assert safe["symbol"] == "BTCUSDT"


def test_market_order_uses_order_endpoint():
    calls = []

    def fake_post(url, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse({"ok": True, "data": {"orderId": 123}})

    result = send_order_via_gateway(
        {
            "symbol": "BTCUSDT",
            "market": "FUTURES",
            "side": "BUY",
            "type": "MARKET",
            "quantity": "0.01",
        },
        post=fake_post,
    )

    assert result["ok"] is True
    assert calls[0]["url"].endswith("/binance/order")


def test_stop_market_uses_algo_order_endpoint():
    calls = []

    def fake_post(url, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse({"ok": True, "data": {"algoId": 123}})

    result = send_order_via_gateway(
        {
            "symbol": "BTCUSDT",
            "market": "FUTURES",
            "side": "SELL",
            "type": "STOP_MARKET",
            "quantity": "0.01",
            "stopPrice": "90000",
            "reduceOnly": True,
        },
        post=fake_post,
    )

    assert result["ok"] is True
    assert calls[0]["url"].endswith("/binance/algo-order")


def test_take_profit_market_uses_algo_order_endpoint():
    calls = []

    def fake_post(url, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse({"ok": True, "data": {"algoId": 456}})

    result = send_order_via_gateway(
        {
            "symbol": "BTCUSDT",
            "market": "FUTURES",
            "side": "SELL",
            "type": "TAKE_PROFIT_MARKET",
            "quantity": "0.01",
            "stopPrice": "120000",
            "reduceOnly": True,
        },
        post=fake_post,
    )

    assert result["ok"] is True
    assert calls[0]["url"].endswith("/binance/algo-order")

def test_algo_order_status_requires_exactly_one_identifier():
    with pytest.raises(ValueError, match="exactly_one_algo_identifier_required"):
        fetch_algo_order_status_via_gateway(
            api_key="k",
            api_secret="s",
            symbol="BTCUSDT",
        )

    with pytest.raises(ValueError, match="exactly_one_algo_identifier_required"):
        fetch_algo_order_status_via_gateway(
            api_key="k",
            api_secret="s",
            symbol="BTCUSDT",
            algo_id=1,
            client_algo_id="abc",
        )


def test_algo_order_status_uses_gateway_endpoint():
    calls = []

    def fake_post(url, json, timeout):
        calls.append(
            {
                "url": url,
                "json": json,
                "timeout": timeout,
            }
        )
        return FakeResponse(
            {
                "ok": True,
                "mode": "gateway_algo_order_status_futures",
                "data": {"algoId": 123},
            }
        )

    result = fetch_algo_order_status_via_gateway(
        api_key="k",
        api_secret="s",
        symbol="BTCUSDT",
        algo_id=123,
        post=fake_post,
    )

    assert result["status"] == "OK"

    assert calls[0]["url"].endswith("/binance/algo-order-status")

    assert calls[0]["json"]["symbol"] == "BTCUSDT"
    assert calls[0]["json"]["algoId"] == 123

    assert "clientAlgoId" not in calls[0]["json"]


def test_algo_order_status_supports_client_algo_id():
    calls = []

    def fake_post(url, json, timeout):
        calls.append(
            {
                "url": url,
                "json": json,
                "timeout": timeout,
            }
        )
        return FakeResponse(
            {
                "ok": True,
                "mode": "gateway_algo_order_status_futures",
                "data": {"clientAlgoId": "cid-123"},
            }
        )

    result = fetch_algo_order_status_via_gateway(
        api_key="k",
        api_secret="s",
        symbol="BTCUSDT",
        client_algo_id="cid-123",
        post=fake_post,
    )

    assert result["status"] == "OK"

    assert calls[0]["json"]["clientAlgoId"] == "cid-123"

    assert "algoId" not in calls[0]["json"]


def test_algo_order_status_timeout_is_not_failed_execution():
    def fake_post(url, json, timeout):
        raise requests.exceptions.ReadTimeout()

    result = fetch_algo_order_status_via_gateway(
        api_key="k",
        api_secret="s",
        symbol="BTCUSDT",
        algo_id=123,
        post=fake_post,
    )

    assert result["status"] == "TIMEOUT"
    assert result["error"] == "gateway_read_timeout"


def test_execute_binance_test_order_for_user_blocks_when_kill_switch_disabled(monkeypatch):
    from fastapi import HTTPException
    import apps.worker.app.engine.execution_runtime as runtime

    class _DB:
        committed = False

        def commit(self):
            self.committed = True

        def close(self):
            pass

    db = _DB()
    audit = {}

    monkeypatch.setattr(runtime, "SessionLocal", lambda: db)
    monkeypatch.setattr(runtime, "get_trading_enabled", lambda db: False)
    monkeypatch.setattr(
        runtime,
        "log_audit_event",
        lambda db, action, user_id, entity_type, details: audit.update(
            {
                "action": action,
                "user_id": user_id,
                "entity_type": entity_type,
                "details": details,
            }
        ),
    )

    try:
        runtime.execute_binance_test_order_for_user("user-1", "BTCUSDT", "BUY", 1.0)
        assert False, "expected kill-switch block"
    except HTTPException as exc:
        assert exc.status_code == 409
        assert exc.detail == "Trading is globally disabled by admin kill-switch"

    assert audit["action"] == "execution.blocked.kill_switch"
    assert audit["user_id"] == "user-1"
    assert audit["details"]["exchange"] == "BINANCE"
    assert audit["details"]["action"] == "execute_binance_test_order_for_user"
    assert db.committed is True

