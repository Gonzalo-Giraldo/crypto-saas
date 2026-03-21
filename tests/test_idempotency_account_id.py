import pytest
from apps.worker.app.engine.minimal_execution_runtime import MinimalExecutionRuntime

@pytest.fixture
def runtime():
    # Se crea una instancia nueva para cada test (store en memoria)
    rt = MinimalExecutionRuntime()
    # Limpiar el store para evitar colisiones entre tests
    rt._idempotency_store.clear()
    return rt

def test_idempotency_duplicate_without_account_id(runtime):
    # CASO 1: misma orden sin account_id repetida
    result1 = runtime.submit_intent(
        user_id="u1",
        strategy_id="s1",
        broker="binance",
        market="spot",
        symbol="BTCUSDT",
        side="BUY",
        quantity=1.0,
        order_ref="ORD-1",
        mode="stub",
        metadata=None,
    )
    result2 = runtime.submit_intent(
        user_id="u1",
        strategy_id="s1",
        broker="binance",
        market="spot",
        symbol="BTCUSDT",
        side="BUY",
        quantity=1.0,
        order_ref="ORD-1",
        mode="stub",
        metadata=None,
    )
    assert result2["idempotency_status"] == "duplicate"

def test_idempotency_duplicate_with_same_account_id(runtime):
    # CASO 2: misma orden con mismo account_id repetida
    meta = {"account_id": "A1"}
    result1 = runtime.submit_intent(
        user_id="u1",
        strategy_id="s1",
        broker="binance",
        market="spot",
        symbol="BTCUSDT",
        side="BUY",
        quantity=1.0,
        order_ref="ORD-2",
        mode="stub",
        metadata=meta,
    )
    result2 = runtime.submit_intent(
        user_id="u1",
        strategy_id="s1",
        broker="binance",
        market="spot",
        symbol="BTCUSDT",
        side="BUY",
        quantity=1.0,
        order_ref="ORD-2",
        mode="stub",
        metadata=meta,
    )
    assert result2["idempotency_status"] == "duplicate"

def test_idempotency_no_duplicate_with_different_account_id(runtime):
    # CASO 3: misma orden con distinto account_id
    meta1 = {"account_id": "A2"}
    meta2 = {"account_id": "A3"}
    result1 = runtime.submit_intent(
        user_id="u1",
        strategy_id="s1",
        broker="binance",
        market="spot",
        symbol="BTCUSDT",
        side="BUY",
        quantity=1.0,
        order_ref="ORD-3",
        mode="stub",
        metadata=meta1,
    )
    result2 = runtime.submit_intent(
        user_id="u1",
        strategy_id="s1",
        broker="binance",
        market="spot",
        symbol="BTCUSDT",
        side="BUY",
        quantity=1.0,
        order_ref="ORD-3",
        mode="stub",
        metadata=meta2,
    )
    assert result2["idempotency_status"] == "ok"

def test_idempotency_no_collision_between_account_id_and_none(runtime):
    # CASO 4: misma orden una vez sin account_id y otra con account_id
    meta = {"account_id": "A4"}
    result1 = runtime.submit_intent(
        user_id="u1",
        strategy_id="s1",
        broker="binance",
        market="spot",
        symbol="BTCUSDT",
        side="BUY",
        quantity=1.0,
        order_ref="ORD-4",
        mode="stub",
        metadata=None,
    )
    result2 = runtime.submit_intent(
        user_id="u1",
        strategy_id="s1",
        broker="binance",
        market="spot",
        symbol="BTCUSDT",
        side="BUY",
        quantity=1.0,
        order_ref="ORD-4",
        mode="stub",
        metadata=meta,
    )
    assert result2["idempotency_status"] == "ok"
