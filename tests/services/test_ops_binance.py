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

def test_close_preflight_trading_disabled(monkeypatch):
    monkeypatch.setattr(module, "get_trading_enabled", lambda db: False)

    result = module.binance_close_preflight(
        symbol="BTCUSDT",
        account_id="default",
        market="FUTURES",
        db="fake-db",
        current_user=SimpleNamespace(id="admin-1", role="admin"),
    )

    assert result["success"] is False
    assert result["classification"] == "TRADING_DISABLED"
    assert result["mutations"] == []


def test_close_preflight_ready_to_close_long(monkeypatch):
    monkeypatch.setattr(module, "get_trading_enabled", lambda db: True)

    monkeypatch.setattr(
        module,
        "get_decrypted_exchange_secret",
        lambda **kwargs: {"api_key": "k", "api_secret": "s"},
    )

    monkeypatch.setattr(
        module,
        "get_binance_positions",
        lambda **kwargs: [
            {
                "symbol": "BTCUSDT",
                "side": "BUY",
                "qty": "0.001",
            }
        ],
    )

    result = module.binance_close_preflight(
        symbol="BTCUSDT",
        account_id="default",
        market="FUTURES",
        db="fake-db",
        current_user=SimpleNamespace(id="admin-1", role="admin"),
    )

    assert result["success"] is True
    assert result["classification"] == "READY_TO_CLOSE"
    assert result["close_side"] == "SELL"
    assert result["reduce_only"] is True
    assert result["mutations"] == []


def test_close_preflight_no_open_position(monkeypatch):
    monkeypatch.setattr(module, "get_trading_enabled", lambda db: True)

    monkeypatch.setattr(
        module,
        "get_decrypted_exchange_secret",
        lambda **kwargs: {"api_key": "k", "api_secret": "s"},
    )

    monkeypatch.setattr(
        module,
        "get_binance_positions",
        lambda **kwargs: [],
    )

    result = module.binance_close_preflight(
        symbol="BTCUSDT",
        account_id="default",
        market="FUTURES",
        db="fake-db",
        current_user=SimpleNamespace(id="admin-1", role="admin"),
    )

    assert result["success"] is False
    assert result["classification"] == "NO_OPEN_POSITION"
    assert result["mutations"] == []

def test_execute_close_requires_idempotency_key():
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        module.binance_execute_close(
            payload=module.BinanceExecuteCloseRequest(
                symbol="BTCUSDT",
                qty=0.001,
                account_id="default",
                market="FUTURES",
                confirm=False,
                execution_authorized=False,
            ),
            db="fake-db",
            current_user=SimpleNamespace(id="admin-1", role="admin"),
            idempotency_key=None,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "idempotency_key_required_for_close_execution"


def test_execute_close_is_blocked_not_implemented_and_idempotent(monkeypatch):
    calls = {"reserve": 0, "finalize": 0, "audit": 0, "commit": 0}

    class _Db:
        def commit(self):
            calls["commit"] += 1

    def fake_reserve(*args, **kwargs):
        assert len(args) == 1
        calls["reserve"] += 1
        assert kwargs["endpoint"] == "/ops/admin/binance/execute-close"
        assert kwargs["idempotency_key"] == "close-key-1"
        return None

    def fake_finalize(*args, **kwargs):
        assert len(args) == 1
        calls["finalize"] += 1
        assert kwargs["endpoint"] == "/ops/admin/binance/execute-close"
        assert kwargs["idempotency_key"] == "close-key-1"
        assert kwargs["response_payload"]["classification"] == "EXPLICIT_CONFIRMATION_REQUIRED"

    def fake_audit(*args, **kwargs):
        calls["audit"] += 1
        assert kwargs["action"] == "execution.binance.close.blocked"

    monkeypatch.setattr(module, "reserve_idempotent_intent", fake_reserve)
    monkeypatch.setattr(module, "finalize_idempotent_intent", fake_finalize)
    monkeypatch.setattr(module, "log_audit_event", fake_audit)

    result = module.binance_execute_close(
        payload=module.BinanceExecuteCloseRequest(
            symbol="BTCUSDT",
            qty=0.001,
            account_id="default",
            market="FUTURES",
            confirm=False,
            execution_authorized=False,
        ),
        db=_Db(),
        current_user=SimpleNamespace(id="admin-1", role="admin"),
        idempotency_key="close-key-1",
    )

    assert result["success"] is False
    assert result["classification"] == "EXPLICIT_CONFIRMATION_REQUIRED"
    assert result["mutations"] == []
    assert calls == {"reserve": 1, "finalize": 1, "audit": 1, "commit": 1}


def test_execute_close_returns_cached_idempotent_response(monkeypatch):
    cached = {
        "success": False,
        "classification": "NOT_IMPLEMENTED_SAFE_STOP",
        "cached": True,
        "mutations": [],
    }

    monkeypatch.setattr(
        module,
        "reserve_idempotent_intent",
        lambda *args, **kwargs: cached,
    )


    result = module.binance_execute_close(
        payload=module.BinanceExecuteCloseRequest(
            symbol="BTCUSDT",
            qty=0.001,
            account_id="default",
            market="FUTURES",
            confirm=False,
            execution_authorized=False,
        ),
        db="fake-db",
        current_user=SimpleNamespace(id="admin-1", role="admin"),
        idempotency_key="close-key-1",
    )

    assert result == cached

def test_resolve_close_context_rejects_qty_mismatch():
    result = module._resolve_binance_close_context(
        positions=[{"symbol": "BTCUSDT", "side": "BUY", "qty": 0.002}],
        symbol="BTCUSDT",
        requested_qty=0.001,
        account_id="default",
        market="FUTURES",
    )

    assert result["success"] is False
    assert result["classification"] == "POSITION_QTY_MISMATCH"
    assert result["mutations"] == []


def test_resolve_close_context_rejects_ambiguous_position_as_hedge_unsupported():
    result = module._resolve_binance_close_context(
        positions=[
            {"symbol": "BTCUSDT", "side": "BUY", "qty": 0.001},
            {"symbol": "BTCUSDT", "side": "SELL", "qty": 0.001},
        ],
        symbol="BTCUSDT",
        requested_qty=0.001,
        account_id="default",
        market="FUTURES",
    )

    assert result["success"] is False
    assert result["classification"] == "HEDGE_MODE_UNSUPPORTED"
    assert result["mutations"] == []


def test_resolve_close_context_derives_sell_for_long():
    result = module._resolve_binance_close_context(
        positions=[{"symbol": "BTCUSDT", "side": "BUY", "qty": 0.001}],
        symbol="BTCUSDT",
        requested_qty=0.001,
        account_id="default",
        market="FUTURES",
    )

    assert result["success"] is True
    assert result["classification"] == "READY_TO_CLOSE"
    assert result["position_direction"] == "LONG"
    assert result["close_side"] == "SELL"
    assert result["reduce_only"] is True


def test_resolve_close_context_derives_buy_for_short():
    result = module._resolve_binance_close_context(
        positions=[{"symbol": "BTCUSDT", "side": "SELL", "qty": 0.001}],
        symbol="BTCUSDT",
        requested_qty=0.001,
        account_id="default",
        market="FUTURES",
    )

    assert result["success"] is True
    assert result["classification"] == "READY_TO_CLOSE"
    assert result["position_direction"] == "SHORT"
    assert result["close_side"] == "BUY"
    assert result["reduce_only"] is True
