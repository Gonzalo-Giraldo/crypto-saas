from types import SimpleNamespace

import apps.api.app.api.ops_binance as module


def test_reconcile_binance_order_rejects_non_futures_market():
    result = module.reconcile_binance_order(
        symbol="btcusdt",
        client_order_id="cid-1",
        account_id="default",
        market="SPOT",
        db="fake-db",
        current_user=SimpleNamespace(id="user-1", role="admin"),
    )

    assert result["success"] is False
    assert result["classification"] == "INVALID_INPUT"
    assert result["error"] == "binance_reconcile_order_supports_futures_only"
    assert result["symbol"] == "BTCUSDT"
    assert result["market"] == "SPOT"


def test_reconcile_binance_order_is_read_only_and_classifies(monkeypatch):
    calls = {"creds": 0, "reconcile": 0}

    def fake_get_decrypted_exchange_secret(**kwargs):
        calls["creds"] += 1
        return {"api_key": "k", "api_secret": "s"}

    def fake_reconcile(**kwargs):
        calls["reconcile"] += 1
        return {
            "result": {"status": "FILLED", "orderId": 123},
            "error": None,
        }

    monkeypatch.setattr(module, "get_decrypted_exchange_secret", fake_get_decrypted_exchange_secret)
    monkeypatch.setattr(module, "_reconcile_binance_test_order_best_effort", fake_reconcile)

    result = module.reconcile_binance_order(
        symbol="btcusdt",
        client_order_id="cid-2",
        account_id="default",
        market="FUTURES",
        db="fake-db",
        current_user=SimpleNamespace(id="user-1", role="admin"),
    )

    assert result["success"] is True
    assert result["classification"] == "EXECUTED"
    assert result["symbol"] == "BTCUSDT"
    assert result["client_order_id"] == "cid-2"
    assert result["market"] == "FUTURES"
    assert result["mutations"] == []
    assert calls == {"creds": 1, "reconcile": 1}


def test_reconcile_binance_intent_returns_not_found(monkeypatch):
    monkeypatch.setattr(module, "get_intent", lambda db, intent_id: None)

    result = module.reconcile_binance_intent(
        intent_id="intent-missing",
        account_id="default",
        db="fake-db",
        current_user=SimpleNamespace(id="admin-1", role="admin"),
    )

    assert result["success"] is False
    assert result["classification"] == "INTENT_NOT_FOUND"
    assert result["mutations"] == []


def test_reconcile_binance_intent_uses_consumption_and_classifies(monkeypatch):
    calls = {"creds": 0, "reconcile": 0}

    intent = SimpleNamespace(
        intent_id="intent-1",
        user_id="user-1",
        broker="BINANCE",
        account_id="default",
        symbol="BTCUSDT",
        lifecycle_status="EXECUTED",
    )

    class _Store:
        def get_consumption_record(self, **kwargs):
            return {
                "found": True,
                "intent_key": "intent-1",
                "broker_execution_id": "cid-intent-1",
                "broker_execution_id_type": "client_order_id",
                "symbol": "BTCUSDT",
                "market": "FUTURES",
            }

    def fake_get_decrypted_exchange_secret(**kwargs):
        calls["creds"] += 1
        return {"api_key": "k", "api_secret": "s"}

    def fake_reconcile(**kwargs):
        calls["reconcile"] += 1
        assert kwargs["client_order_id"] == "cid-intent-1"
        assert kwargs["symbol"] == "BTCUSDT"
        assert kwargs["market"] == "FUTURES"
        return {
            "result": {"status": "FILLED", "orderId": 123},
            "error": None,
        }

    monkeypatch.setattr(module, "get_intent", lambda db, intent_id: intent)
    monkeypatch.setattr(module, "IntentConsumptionStore", lambda: _Store())
    monkeypatch.setattr(module, "get_decrypted_exchange_secret", fake_get_decrypted_exchange_secret)
    monkeypatch.setattr(module, "_reconcile_binance_test_order_best_effort", fake_reconcile)

    result = module.reconcile_binance_intent(
        intent_id="intent-1",
        account_id="default",
        db="fake-db",
        current_user=SimpleNamespace(id="admin-1", role="admin"),
    )

    assert result["success"] is True
    assert result["classification"] == "EXECUTED"
    assert result["intent_id"] == "intent-1"
    assert result["execution_ref"] == "cid-intent-1"
    assert result["execution_ref_type"] == "client_order_id"
    assert result["mutations"] == []
    assert calls == {"creds": 1, "reconcile": 1}
