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

def test_reconcile_binance_intent_uses_order_id_helper_for_order_id_refs(monkeypatch):
    calls = {"creds": 0, "client_reconcile": 0, "order_id_reconcile": 0}

    intent = SimpleNamespace(
        intent_id="intent-order-id",
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
                "intent_key": "intent-order-id",
                "broker_execution_id": "1010471699629",
                "broker_execution_id_type": "orderId",
                "symbol": "BTCUSDT",
                "market": "FUTURES",
            }

    def fake_get_decrypted_exchange_secret(**kwargs):
        calls["creds"] += 1
        return {"api_key": "k", "api_secret": "s"}

    def fake_client_reconcile(**kwargs):
        calls["client_reconcile"] += 1
        raise AssertionError("client_order_id reconciliation must not be used for orderId refs")

    def fake_order_id_reconcile(**kwargs):
        calls["order_id_reconcile"] += 1
        assert kwargs["order_id"] == "1010471699629"
        assert kwargs["symbol"] == "BTCUSDT"
        assert kwargs["market"] == "FUTURES"
        return {"status": "FILLED", "orderId": 1010471699629}

    monkeypatch.setattr(module, "get_intent", lambda db, intent_id: intent)
    monkeypatch.setattr(module, "IntentConsumptionStore", lambda: _Store())
    monkeypatch.setattr(module, "get_decrypted_exchange_secret", fake_get_decrypted_exchange_secret)
    monkeypatch.setattr(module, "_reconcile_binance_test_order_best_effort", fake_client_reconcile)
    monkeypatch.setattr(module, "query_order_status_by_order_id", fake_order_id_reconcile)

    result = module.reconcile_binance_intent(
        intent_id="intent-order-id",
        account_id="default",
        db="fake-db",
        current_user=SimpleNamespace(id="admin-1", role="admin"),
    )

    assert result["success"] is True
    assert result["classification"] == "EXECUTED"
    assert result["execution_ref"] == "1010471699629"
    assert result["execution_ref_type"] == "orderId"
    assert result["mutations"] == []
    assert calls == {"creds": 1, "client_reconcile": 0, "order_id_reconcile": 1}

def test_reconcile_binance_position_open_position(monkeypatch):
    calls = {"creds": 0, "positions": 0}

    def fake_get_decrypted_exchange_secret(**kwargs):
        calls["creds"] += 1
        return {"api_key": "k", "api_secret": "s"}

    def fake_get_binance_positions(**kwargs):
        calls["positions"] += 1
        return [
            {
                "broker": "BINANCE",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "qty": 0.001,
                "entry_price": 80939.2,
                "current_price": 81200.0,
                "unrealized_pnl": 0.26,
            }
        ]

    monkeypatch.setattr(module, "get_decrypted_exchange_secret", fake_get_decrypted_exchange_secret)
    monkeypatch.setattr(module, "get_binance_positions", fake_get_binance_positions)

    result = module.reconcile_binance_position(
        symbol="BTCUSDT",
        account_id="default",
        market="FUTURES",
        db="fake-db",
        current_user=SimpleNamespace(id="admin-1", role="admin"),
    )

    assert result["success"] is True
    assert result["classification"] == "OPEN_POSITION"
    assert result["protected"] == "UNKNOWN"
    assert result["mutations"] == []
    assert result["position"]["symbol"] == "BTCUSDT"
    assert calls == {"creds": 1, "positions": 1}


def test_reconcile_binance_position_no_open_position(monkeypatch):
    def fake_get_decrypted_exchange_secret(**kwargs):
        return {"api_key": "k", "api_secret": "s"}

    monkeypatch.setattr(module, "get_decrypted_exchange_secret", fake_get_decrypted_exchange_secret)
    monkeypatch.setattr(module, "get_binance_positions", lambda **kwargs: [])

    result = module.reconcile_binance_position(
        symbol="BTCUSDT",
        account_id="default",
        market="FUTURES",
        db="fake-db",
        current_user=SimpleNamespace(id="admin-1", role="admin"),
    )

    assert result["success"] is True
    assert result["classification"] == "NO_OPEN_POSITION"
    assert result["position"] is None
    assert result["protected"] == "UNKNOWN"
    assert result["mutations"] == []


def test_reconcile_binance_position_handles_position_unknown(monkeypatch):
    def fake_get_decrypted_exchange_secret(**kwargs):
        return {"api_key": "k", "api_secret": "s"}

    def fake_get_binance_positions(**kwargs):
        raise RuntimeError("gateway timeout")

    monkeypatch.setattr(module, "get_decrypted_exchange_secret", fake_get_decrypted_exchange_secret)
    monkeypatch.setattr(module, "get_binance_positions", fake_get_binance_positions)

    result = module.reconcile_binance_position(
        symbol="BTCUSDT",
        account_id="default",
        market="FUTURES",
        db="fake-db",
        current_user=SimpleNamespace(id="admin-1", role="admin"),
    )

    assert result["success"] is False
    assert result["classification"] == "POSITION_UNKNOWN"
    assert result["mutations"] == []

