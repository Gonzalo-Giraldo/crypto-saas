import pytest
from apps.worker.app.engine.ibkr_client import generate_order_ref

def test_generate_order_ref_from_intent_key_full_context():
    ref1 = generate_order_ref(intent_key="INTENT-1", user_id="U1", broker="BINANCE", account_id="A1")
    ref2 = generate_order_ref(intent_key="INTENT-1", user_id="U1", broker="BINANCE", account_id="A1")
    assert ref1 == ref2
    # Cambia user_id
    ref3 = generate_order_ref(intent_key="INTENT-1", user_id="U2", broker="BINANCE", account_id="A1")
    assert ref1 != ref3
    # Cambia account_id
    ref4 = generate_order_ref(intent_key="INTENT-1", user_id="U1", broker="BINANCE", account_id="A2")
    assert ref1 != ref4
    # Cambia broker
    ref5 = generate_order_ref(intent_key="INTENT-1", user_id="U1", broker="IBKR", account_id="A1")
    assert ref1 != ref5

def test_generate_order_ref_from_intent_key_missing_account():
    ref1 = generate_order_ref(intent_key="INTENT-2", user_id="U1", broker="BINANCE", account_id=None)
    ref2 = generate_order_ref(intent_key="INTENT-2", user_id="U1", broker="BINANCE")
    assert ref1 == ref2
    assert ref1.endswith("::no-account")

def test_generate_order_ref_from_intent_key_strips():
    ref = generate_order_ref(intent_key="  INTENT-3  ", user_id="  U1  ", broker="BINANCE", account_id="  A1  ")
    # Debe strippear intent_key y account_id
    assert ref.startswith("INTENT-3")
    assert ref.endswith("A1")

def test_generate_order_ref_fallback():
    # Sin intent_key, debe usar fallback determinístico
    ref = generate_order_ref(user_id="U1", strategy_id="S1", symbol="BTCUSDT", side="BUY")
    assert ref == "U1-S1-BTCUSDT-BUY"

def test_generate_order_ref_explicit_order_ref_priority():
    # Si se pasa order_ref explícita, debe tener prioridad
    ref = generate_order_ref(order_ref="  ORD-EXPL  ", intent_key="INTENT-4", user_id="U1", broker="BINANCE", account_id="A1")
    assert ref == "ORD-EXPL"