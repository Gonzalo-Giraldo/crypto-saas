import apps.worker.app.engine.execution_runtime as runtime

def test_runtime_wires_exit_order_creation_once(monkeypatch):
    class _DB:

        def execute(self, *args, **kwargs):
            class _Result:
                def fetchone(self):
                    return (1,)

                def scalar_one_or_none(self):
                    return None

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
            return {"accepted": True}

    create_calls = {"count": 0}

    monkeypatch.setattr(runtime, "SessionLocal", lambda: _DB())
    monkeypatch.setattr(runtime, "_assert_binance_gateway_policy", lambda: None)

    monkeypatch.setattr(
        runtime,
        "get_decrypted_exchange_secret",
        lambda db, user_id, exchange: {
            "api_key": "k",
            "api_secret": "s",
        },
    )

    import apps.api.app.services.exchange_secrets as exchange_secrets_module

    monkeypatch.setattr(
        exchange_secrets_module,
        "get_decrypted_exchange_secret",
        lambda db, user_id, exchange: {
            "api_key": "k",
            "api_secret": "s",
        },
    )

    import apps.api.app.services.binance_fill_manual_runner as fill_runner
    import apps.api.app.services.binance_trades_gateway_client as trades_client
    import apps.api.app.services.binance_fill_db as fill_db

    monkeypatch.setattr(
        fill_runner,
        "run_binance_fill_ingestion_for_intent",
        lambda **kwargs: {
            "trades": [
                {
                    "price": "100000",
                    "qty": "0.001",
                }
            ],
            "matched_count": 1,
            "attempt": 1,
            "reconciliation": {
                "status": "MATCHED",
            },
        },
    )

    monkeypatch.setattr(
        trades_client,
        "fetch_binance_trades",
        lambda **kwargs: [],
    )

    monkeypatch.setattr(
        fill_db,
        "persist_binance_fills_db",
        lambda **kwargs: None,
    )

    monkeypatch.setattr(
        runtime,
        "prepare_binance_market_order_quantity",
        lambda symbol, requested_qty, market: {
            "normalized_qty": requested_qty,
        },
    )

    monkeypatch.setattr(
        runtime,
        "_build_binance_client_order_id",
        lambda **kwargs: "cid-exit-wire-1",
    )

    monkeypatch.setattr(
        runtime,
        "_build_binance_broker_adapter",
        lambda **kwargs: _Adapter(),
    )

    class _IntentStore:
        def attach_execution(self, **kwargs):
            return True

    monkeypatch.setattr(
        runtime,
        "IntentConsumptionStore",
        lambda: _IntentStore(),
    )

    monkeypatch.setattr(
        runtime,
        "query_order_status",
        lambda **kwargs: {
            "status": "FILLED",
            "orderId": "oid-1",
        },
    )

    monkeypatch.setattr(
        runtime,
        "mark_intent_executed",
        lambda *a, **k: None,
    )

    monkeypatch.setattr(
        runtime,
        "derive_binance_entry_fill_basis",
        lambda **kwargs: {
            "avg_entry_price": "100000",
            "filled_qty": "0.001",
        },
    )

    import apps.worker.app.engine.binance_exit_plan as exit_plan_module

    monkeypatch.setattr(
        exit_plan_module,
        "build_binance_exit_plan",
        lambda **kwargs: {
            "available": True,
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "filled_qty": "0.001",
            "avg_entry_price": "100000",
            "stop_loss": "99000",
            "take_profit": "101000",
            "client_order_id": "cid-exit-wire-1",
        },
    )

    class _Guard:
        allowed = True
        reason = None
        exit_side = "SELL"
        qty = "0.001"
        exit_key = "exit-key-1"

    import apps.worker.app.engine.binance_exit_guard as exit_guard_module

    monkeypatch.setattr(
        exit_guard_module,
        "guard_binance_exit",
        lambda **kwargs: _Guard(),
    )

    class _Bracket:
        stop_loss_order = {
            "type": "STOP_MARKET",
            "clientAlgoId": "sl-1",
        }

        take_profit_order = {
            "type": "TAKE_PROFIT_MARKET",
            "clientAlgoId": "tp-1",
        }

    import apps.worker.app.engine.binance_futures_exit_orders as exit_orders_module

    monkeypatch.setattr(
        exit_orders_module,
        "build_binance_futures_bracket_orders",
        lambda **kwargs: _Bracket(),
    )

    import apps.worker.app.engine.binance_exit_executor as exit_executor_module

    monkeypatch.setattr(
        exit_executor_module,
        "create_exit_orders",
        lambda **kwargs: create_calls.__setitem__(
            "count",
            create_calls["count"] + 1,
        ) or {
            "sl": {"clientAlgoId": "sl-1"},
            "tp": {"clientAlgoId": "tp-1"},
        },
    )

    runtime.execute_binance_real_order_for_user(
        user_id="user-1",
        symbol="BTCUSDT",
        side="BUY",
        qty=0.001,
        intent_key="intent-exit-wire-1",
        account_id="default",
        market="FUTURES",
    )

    assert create_calls["count"] == 1

def test_runtime_blocks_persist_when_exit_creation_fails(monkeypatch):
    class _DB:

        def execute(self, *args, **kwargs):
            class _Result:
                def fetchone(self):
                    return (1,)

                def scalar_one_or_none(self):
                    return None

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
            return {"accepted": True}

    persist_called = {"value": False}

    monkeypatch.setattr(runtime, "SessionLocal", lambda: _DB())
    monkeypatch.setattr(runtime, "_assert_binance_gateway_policy", lambda: None)

    monkeypatch.setattr(
        runtime,
        "get_decrypted_exchange_secret",
        lambda db, user_id, exchange: {
            "api_key": "k",
            "api_secret": "s",
        },
    )

    import apps.api.app.services.exchange_secrets as exchange_secrets_module

    monkeypatch.setattr(
        exchange_secrets_module,
        "get_decrypted_exchange_secret",
        lambda db, user_id, exchange: {
            "api_key": "k",
            "api_secret": "s",
        },
    )

    import apps.api.app.services.binance_fill_manual_runner as fill_runner
    import apps.api.app.services.binance_trades_gateway_client as trades_client
    import apps.api.app.services.binance_fill_db as fill_db

    monkeypatch.setattr(
        fill_runner,
        "run_binance_fill_ingestion_for_intent",
        lambda **kwargs: {
            "trades": [
                {
                    "price": "100000",
                    "qty": "0.001",
                }
            ],
            "matched_count": 1,
            "attempt": 1,
            "reconciliation": {
                "status": "MATCHED",
            },
        },
    )

    monkeypatch.setattr(
        trades_client,
        "fetch_binance_trades",
        lambda **kwargs: [],
    )

    monkeypatch.setattr(
        fill_db,
        "persist_binance_fills_db",
        lambda **kwargs: None,
    )

    monkeypatch.setattr(
        runtime,
        "prepare_binance_market_order_quantity",
        lambda symbol, requested_qty, market: {
            "normalized_qty": requested_qty,
        },
    )

    monkeypatch.setattr(
        runtime,
        "_build_binance_client_order_id",
        lambda **kwargs: "cid-exit-wire-2",
    )

    monkeypatch.setattr(
        runtime,
        "_build_binance_broker_adapter",
        lambda **kwargs: _Adapter(),
    )

    class _IntentStore:
        def attach_execution(self, **kwargs):
            return True

    monkeypatch.setattr(
        runtime,
        "IntentConsumptionStore",
        lambda: _IntentStore(),
    )

    monkeypatch.setattr(
        runtime,
        "query_order_status",
        lambda **kwargs: {
            "status": "FILLED",
            "orderId": "oid-2",
        },
    )

    monkeypatch.setattr(
        runtime,
        "mark_intent_executed",
        lambda *a, **k: None,
    )

    monkeypatch.setattr(
        runtime,
        "derive_binance_entry_fill_basis",
        lambda **kwargs: {
            "avg_entry_price": "100000",
            "filled_qty": "0.001",
        },
    )

    import apps.worker.app.engine.binance_exit_plan as exit_plan_module

    monkeypatch.setattr(
        exit_plan_module,
        "build_binance_exit_plan",
        lambda **kwargs: {
            "available": True,
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "filled_qty": "0.001",
            "avg_entry_price": "100000",
            "stop_loss": "99000",
            "take_profit": "101000",
            "client_order_id": "cid-exit-wire-2",
        },
    )

    class _Guard:
        allowed = True
        reason = None
        exit_side = "SELL"
        qty = "0.001"
        exit_key = "exit-key-2"

    import apps.worker.app.engine.binance_exit_guard as exit_guard_module

    monkeypatch.setattr(
        exit_guard_module,
        "guard_binance_exit",
        lambda **kwargs: _Guard(),
    )

    class _Bracket:
        stop_loss_order = {
            "type": "STOP_MARKET",
            "clientAlgoId": "sl-2",
        }

        take_profit_order = {
            "type": "TAKE_PROFIT_MARKET",
            "clientAlgoId": "tp-2",
        }

    import apps.worker.app.engine.binance_futures_exit_orders as exit_orders_module

    monkeypatch.setattr(
        exit_orders_module,
        "build_binance_futures_bracket_orders",
        lambda **kwargs: _Bracket(),
    )

    import apps.worker.app.engine.binance_exit_executor as exit_executor_module

    monkeypatch.setattr(
        exit_executor_module,
        "create_exit_orders",
        lambda **kwargs: {
            "sl": None,
            "tp": None,
            "error": "stop_loss_failed",
        },
    )

    import apps.api.app.services.binance_exit_protection_service as protection_module

    monkeypatch.setattr(
        protection_module,
        "create_exit_protection",
        lambda *a, **k: persist_called.__setitem__("value", True),
    )

    runtime.execute_binance_real_order_for_user(
        user_id="user-1",
        symbol="BTCUSDT",
        side="BUY",
        qty=0.001,
        intent_key="intent-exit-wire-2",
        account_id="default",
        market="FUTURES",
    )

    assert persist_called["value"] is False

def test_runtime_logs_post_fill_exit_diff_observability(monkeypatch):
    class _DB:

        def execute(self, *args, **kwargs):
            class _Result:
                def fetchone(self):
                    return (1,)

                def scalar_one_or_none(self):
                    return None

            return _Result()

        def add(self, obj):
            return None

        def flush(self):
            return None

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    class _Adapter:
        def send_order(self, **kwargs):
            return {"accepted": True}

    audit_events = []
    post_fill_calls = {"count": 0}
    diff_calls = {"count": 0}

    monkeypatch.setattr(runtime, "SessionLocal", lambda: _DB())
    monkeypatch.setattr(runtime, "_assert_binance_gateway_policy", lambda: None)
    monkeypatch.setattr(
        runtime,
        "log_audit_event",
        lambda db, action, user_id, entity_type, details: audit_events.append(
            {
                "action": action,
                "details": details,
            }
        ),
    )

    monkeypatch.setattr(
        runtime,
        "get_decrypted_exchange_secret",
        lambda db, user_id, exchange: {"api_key": "k", "api_secret": "s"},
    )

    import apps.api.app.services.exchange_secrets as exchange_secrets_module

    monkeypatch.setattr(
        exchange_secrets_module,
        "get_decrypted_exchange_secret",
        lambda db, user_id, exchange: {"api_key": "k", "api_secret": "s"},
    )

    import apps.api.app.services.binance_fill_manual_runner as fill_runner
    import apps.api.app.services.binance_trades_gateway_client as trades_client
    import apps.api.app.services.binance_fill_db as fill_db

    monkeypatch.setattr(
        fill_runner,
        "run_binance_fill_ingestion_for_intent",
        lambda **kwargs: {
            "trades": [{"price": "101000", "qty": "0.001"}],
            "matched_count": 1,
            "attempt": 1,
            "reconciliation": {"status": "MATCHED"},
        },
    )
    monkeypatch.setattr(trades_client, "fetch_binance_trades", lambda **kwargs: [])
    monkeypatch.setattr(fill_db, "persist_binance_fills_db", lambda **kwargs: None)

    monkeypatch.setattr(
        runtime,
        "prepare_binance_market_order_quantity",
        lambda symbol, requested_qty, market: {"normalized_qty": requested_qty},
    )
    monkeypatch.setattr(
        runtime,
        "_build_binance_client_order_id",
        lambda **kwargs: "cid-exit-wire-3",
    )
    monkeypatch.setattr(runtime, "_build_binance_broker_adapter", lambda **kwargs: _Adapter())

    class _IntentStore:
        def attach_execution(self, **kwargs):
            return True

    monkeypatch.setattr(runtime, "IntentConsumptionStore", lambda: _IntentStore())
    monkeypatch.setattr(
        runtime,
        "query_order_status",
        lambda **kwargs: {"status": "FILLED", "orderId": "oid-3"},
    )
    monkeypatch.setattr(runtime, "mark_intent_executed", lambda *a, **k: None)

    monkeypatch.setattr(
        runtime,
        "derive_binance_entry_fill_basis",
        lambda **kwargs: {
            "avg_entry_price": "101000",
            "filled_qty": "0.001",
            "usable_for_exits": True,
        },
    )

    import apps.api.app.services.risk.post_fill_exit_plan as post_fill_plan_module
    import apps.api.app.services.risk.post_fill_exit_diff as post_fill_diff_module

    class _AuthoritativePlan:
        stop_loss = 99990.0
        take_profit = 103020.0

    def _build_post_fill_plan(**kwargs):
        post_fill_calls["count"] += 1
        assert kwargs["side"] == "BUY"
        assert kwargs["avg_entry_price"] == 101000.0
        assert kwargs["risk_pct"] == 1.0
        assert kwargs["reward_risk_ratio"] == 2.0
        return _AuthoritativePlan()

    def _compare_diff(**kwargs):
        diff_calls["count"] += 1
        assert kwargs["provisional_stop_loss"] == 99000.0
        assert kwargs["provisional_take_profit"] == 102000.0
        assert kwargs["authoritative_stop_loss"] == 99990.0
        assert kwargs["authoritative_take_profit"] == 103020.0

        class _Diff:
            sl_diff_abs = 990.0
            tp_diff_abs = 1020.0
            sl_diff_pct = 1.0
            tp_diff_pct = 1.0
            min_diff_pct = 0.5
            correction_required = True

        return _Diff()

    monkeypatch.setattr(
        post_fill_plan_module,
        "build_post_fill_reward_risk_plan",
        _build_post_fill_plan,
    )
    monkeypatch.setattr(
        post_fill_diff_module,
        "compare_post_fill_exit_plan_diff",
        _compare_diff,
    )

    import apps.worker.app.engine.binance_exit_plan as exit_plan_module

    monkeypatch.setattr(
        exit_plan_module,
        "build_binance_exit_plan",
        lambda **kwargs: {
            "available": True,
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "filled_qty": "0.001",
            "avg_entry_price": "101000",
            "stop_loss": "99000",
            "take_profit": "102000",
            "client_order_id": "cid-exit-wire-3",
        },
    )

    class _Guard:
        allowed = True
        reason = None
        exit_side = "SELL"
        qty = "0.001"
        exit_key = "exit-key-3"

    import apps.worker.app.engine.binance_exit_guard as exit_guard_module

    monkeypatch.setattr(exit_guard_module, "guard_binance_exit", lambda **kwargs: _Guard())

    class _Bracket:
        stop_loss_order = {"type": "STOP_MARKET", "clientAlgoId": "sl-3"}
        take_profit_order = {"type": "TAKE_PROFIT_MARKET", "clientAlgoId": "tp-3"}

    import apps.worker.app.engine.binance_futures_exit_orders as exit_orders_module
    import apps.worker.app.engine.binance_exit_executor as exit_executor_module

    monkeypatch.setattr(
        exit_orders_module,
        "build_binance_futures_bracket_orders",
        lambda **kwargs: _Bracket(),
    )
    monkeypatch.setattr(
        exit_executor_module,
        "create_exit_orders",
        lambda **kwargs: {"sl": {"clientAlgoId": "sl-3"}, "tp": {"clientAlgoId": "tp-3"}},
    )

    runtime.execute_binance_real_order_for_user(
        user_id="user-1",
        symbol="BTCUSDT",
        side="BUY",
        qty=0.001,
        intent_key="intent-exit-wire-3",
        account_id="default",
        market="FUTURES",
        risk_decision={
            "stop_loss": 99000.0,
            "take_profit": 102000.0,
            "expected_qty": 0.001,
            "risk_pct": 1.0,
            "reward_risk_ratio": 2.0,
        },
    )

    assert post_fill_calls["count"] == 1
    assert diff_calls["count"] == 1
    assert any(
        event["action"] == "execution.binance.post_fill_exit_diff"
        and event["details"]["correction_required"] is True
        for event in audit_events
    )

def test_runtime_skips_post_fill_exit_diff_when_reconciliation_not_matched(monkeypatch):
    class _DB:

        def execute(self, *args, **kwargs):
            class _Result:
                def fetchone(self):
                    return (1,)

                def scalar_one_or_none(self):
                    return None

            return _Result()

        def add(self, obj):
            return None

        def flush(self):
            return None

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    class _Adapter:
        def send_order(self, **kwargs):
            return {"accepted": True}

    post_fill_calls = {"count": 0}
    diff_calls = {"count": 0}

    monkeypatch.setattr(runtime, "SessionLocal", lambda: _DB())
    monkeypatch.setattr(runtime, "_assert_binance_gateway_policy", lambda: None)
    monkeypatch.setattr(runtime, "log_audit_event", lambda *a, **k: None)

    monkeypatch.setattr(
        runtime,
        "get_decrypted_exchange_secret",
        lambda db, user_id, exchange: {"api_key": "k", "api_secret": "s"},
    )

    import apps.api.app.services.exchange_secrets as exchange_secrets_module

    monkeypatch.setattr(
        exchange_secrets_module,
        "get_decrypted_exchange_secret",
        lambda db, user_id, exchange: {"api_key": "k", "api_secret": "s"},
    )

    import apps.api.app.services.binance_fill_manual_runner as fill_runner
    import apps.api.app.services.binance_trades_gateway_client as trades_client
    import apps.api.app.services.binance_fill_db as fill_db

    monkeypatch.setattr(
        fill_runner,
        "run_binance_fill_ingestion_for_intent",
        lambda **kwargs: {
            "trades": [{"price": "101000", "qty": "0.001"}],
            "matched_count": 1,
            "attempt": 1,
            "reconciliation": {"status": "PARTIAL"},
        },
    )
    monkeypatch.setattr(trades_client, "fetch_binance_trades", lambda **kwargs: [])
    monkeypatch.setattr(fill_db, "persist_binance_fills_db", lambda **kwargs: None)

    monkeypatch.setattr(
        runtime,
        "prepare_binance_market_order_quantity",
        lambda symbol, requested_qty, market: {"normalized_qty": requested_qty},
    )
    monkeypatch.setattr(
        runtime,
        "_build_binance_client_order_id",
        lambda **kwargs: "cid-exit-wire-4",
    )
    monkeypatch.setattr(
        runtime,
        "_build_binance_broker_adapter",
        lambda **kwargs: _Adapter(),
    )

    class _IntentStore:
        def attach_execution(self, **kwargs):
            return True

    monkeypatch.setattr(runtime, "IntentConsumptionStore", lambda: _IntentStore())
    monkeypatch.setattr(
        runtime,
        "query_order_status",
        lambda **kwargs: {"status": "FILLED", "orderId": "oid-4"},
    )
    monkeypatch.setattr(runtime, "mark_intent_executed", lambda *a, **k: None)

    monkeypatch.setattr(
        runtime,
        "derive_binance_entry_fill_basis",
        lambda **kwargs: {
            "avg_entry_price": "101000",
            "filled_qty": "0.001",
            "usable_for_exits": True,
        },
    )

    import apps.api.app.services.risk.post_fill_exit_plan as post_fill_plan_module
    import apps.api.app.services.risk.post_fill_exit_diff as post_fill_diff_module

    monkeypatch.setattr(
        post_fill_plan_module,
        "build_post_fill_reward_risk_plan",
        lambda **kwargs: post_fill_calls.__setitem__(
            "count",
            post_fill_calls["count"] + 1,
        ),
    )
    monkeypatch.setattr(
        post_fill_diff_module,
        "compare_post_fill_exit_plan_diff",
        lambda **kwargs: diff_calls.__setitem__(
            "count",
            diff_calls["count"] + 1,
        ),
    )

    import apps.worker.app.engine.binance_exit_plan as exit_plan_module

    monkeypatch.setattr(
        exit_plan_module,
        "build_binance_exit_plan",
        lambda **kwargs: {
            "available": True,
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "filled_qty": "0.001",
            "avg_entry_price": "101000",
            "stop_loss": "99000",
            "take_profit": "102000",
            "client_order_id": "cid-exit-wire-4",
        },
    )

    class _Guard:
        allowed = True
        reason = None
        exit_side = "SELL"
        qty = "0.001"
        exit_key = "exit-key-4"

    import apps.worker.app.engine.binance_exit_guard as exit_guard_module

    monkeypatch.setattr(
        exit_guard_module,
        "guard_binance_exit",
        lambda **kwargs: _Guard(),
    )

    class _Bracket:
        stop_loss_order = {"type": "STOP_MARKET", "clientAlgoId": "sl-4"}
        take_profit_order = {"type": "TAKE_PROFIT_MARKET", "clientAlgoId": "tp-4"}

    import apps.worker.app.engine.binance_futures_exit_orders as exit_orders_module
    import apps.worker.app.engine.binance_exit_executor as exit_executor_module

    monkeypatch.setattr(
        exit_orders_module,
        "build_binance_futures_bracket_orders",
        lambda **kwargs: _Bracket(),
    )
    monkeypatch.setattr(
        exit_executor_module,
        "create_exit_orders",
        lambda **kwargs: {
            "sl": {"clientAlgoId": "sl-4"},
            "tp": {"clientAlgoId": "tp-4"},
        },
    )

    runtime.execute_binance_real_order_for_user(
        user_id="user-1",
        symbol="BTCUSDT",
        side="BUY",
        qty=0.001,
        intent_key="intent-exit-wire-4",
        account_id="default",
        market="FUTURES",
        risk_decision={
            "stop_loss": 99000.0,
            "take_profit": 102000.0,
            "expected_qty": 0.001,
            "risk_pct": 1.0,
            "reward_risk_ratio": 2.0,
        },
    )

    assert post_fill_calls["count"] == 0
    assert diff_calls["count"] == 0
