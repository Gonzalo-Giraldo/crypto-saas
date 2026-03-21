import pytest
from apps.worker.app.engine.minimal_execution_runtime import normalize_order_ref, MinimalExecutionRuntime
from apps.worker.app.engine.ibkr_client import _build_order_ref

def test_normalize_order_ref_strips_spaces():
    assert normalize_order_ref("  ORD-1  ") == "ORD-1"
    assert normalize_order_ref("ORD-1") == "ORD-1"
    assert normalize_order_ref("   ") is None
    assert normalize_order_ref(None) is None

def test_minimal_execution_runtime_submit_intent_strips_order_ref():
    runtime = MinimalExecutionRuntime()
    result = runtime.submit_intent(
        user_id="u1",
        strategy_id="s1",
        broker="binance",
        market="spot",
        symbol="BTCUSDT",
        side="BUY",
        quantity=1.0,
        order_ref="  ORD-2  ",
        mode="stub",
        metadata=None,
    )
    assert result["order_ref"] == "ORD-2"
    # El intent_id también debe usar el valor normalizado
    assert result["intent_id"] == "u1:ORD-2"

def test_minimal_execution_runtime_submit_intent_empty_order_ref():
    runtime = MinimalExecutionRuntime()
    result = runtime.submit_intent(
        user_id="u1",
        strategy_id="s1",
        broker="binance",
        market="spot",
        symbol="BTCUSDT",
        side="BUY",
        quantity=1.0,
        order_ref="   ",
        mode="stub",
        metadata=None,
    )
    assert result["accepted"] is False
    assert "order_ref" in result["reason"]

def test_ibkr_build_order_ref_strips_spaces():
    # Si se pasa order_ref externa con espacios, debe normalizar
    assert _build_order_ref(order_ref="  ORD-3  ") == "ORD-3"
    # Si ya está normalizada, no cambia
    assert _build_order_ref(order_ref="ORD-3") == "ORD-3"
    # Si es vacío tras strip, debe seguir la lógica de fallback
    assert _build_order_ref(order_ref="   ", user_id="u", symbol="A", side="B") == "u-A-B"
    # Si es None, debe seguir la lógica de fallback
    assert _build_order_ref(order_ref=None, user_id="u", symbol="A", side="B") == "u-A-B"
