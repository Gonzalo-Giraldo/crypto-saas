def test_list_recent_consumptions_empty(temp_store):
    store = temp_store
    result = store.list_recent_consumptions()
    assert isinstance(result, list)
    assert len(result) == 0

def test_list_recent_consumptions_multiple(temp_store):
    store = temp_store
    # Insertar 3 consumos
    store.register_consumption('u1', 'BINANCE', 'IK1', 'A1')
    store.register_consumption('u2', 'BINANCE', 'IK2', 'A2')
    store.register_consumption('u3', 'BINANCE', 'IK3', 'A3')
    result = store.list_recent_consumptions()
    assert len(result) == 3
    keys = set((r['intent_key'], r['user_id'], r['broker'], r['account_id']) for r in result)
    assert ('IK1', 'u1', 'BINANCE', 'A1') in keys
    assert ('IK2', 'u2', 'BINANCE', 'A2') in keys
    assert ('IK3', 'u3', 'BINANCE', 'A3') in keys
    # Check consumed_at is present and is a string in ISO format
    for r in result:
        assert isinstance(r['consumed_at'], str)
        assert r['consumed_at'].endswith('Z')

def test_list_recent_consumptions_limit(temp_store):
    store = temp_store
    # Insertar 5 consumos
    for i in range(5):
        store.register_consumption(f'u{i}', 'BINANCE', f'IK{i}', f'A{i}')
    result = store.list_recent_consumptions(limit=2)
    assert len(result) == 2
import pytest
import os
import sys
import tempfile
import shutil
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from apps.worker.app.engine.minimal_execution_runtime import IntentConsumptionStore, build_intent_consumption_key

@pytest.fixture
def temp_store(monkeypatch):
    # Usar un directorio temporal para el archivo de store
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, '.intent_consumption_store.json')
    monkeypatch.setattr(IntentConsumptionStore, '_build_store_path', lambda self: path)
    store = IntentConsumptionStore()
    yield store
    shutil.rmtree(tmpdir)

def test_get_consumption_record_found_and_not_found(temp_store):
    store = temp_store
    # Caso no encontrado
    r = store.get_consumption_record('u1', 'BINANCE', 'IKX', 'A1')
    assert r["found"] is False
    assert r["intent_key"] == "IKX"
    assert r["user_id"] == "u1"
    assert r["broker"] == "BINANCE"
    assert r["account_id"] == "A1"
    assert r["consumed_at"] is None
    # Caso encontrado
    store.register_consumption('u1', 'BINANCE', 'IKX', 'A1')
    r2 = store.get_consumption_record('u1', 'BINANCE', 'IKX', 'A1')
    assert r2["found"] is True
    assert r2["intent_key"] == "IKX"
    assert r2["user_id"] == "u1"
    assert r2["broker"] == "BINANCE"
    assert r2["account_id"] == "A1"
    assert isinstance(r2["consumed_at"], str)
    assert r2["consumed_at"].endswith('Z')
def test_consumed_at_persisted_and_exposed(temp_store):
    store = temp_store
    store.register_consumption('u1', 'BINANCE', 'IKZ', 'A1')
    rec = store.get_consumption_record('u1', 'BINANCE', 'IKZ', 'A1')
    assert rec["found"] is True
    assert isinstance(rec["consumed_at"], str)
    assert rec["consumed_at"].endswith('Z')
    # Should also appear in list_recent_consumptions
    found = False
    for r in store.list_recent_consumptions():
        if r['intent_key'] == 'IKZ' and r['user_id'] == 'u1':
            assert isinstance(r['consumed_at'], str)
            assert r['consumed_at'].endswith('Z')
            found = True
    assert found

def test_consumption_same_context_blocked(temp_store):
    store = temp_store
    key = build_intent_consumption_key('u1', 'BINANCE', 'IK1', 'A1')
    assert not store.has_consumed('u1', 'BINANCE', 'IK1', 'A1')
    store.register_consumption('u1', 'BINANCE', 'IK1', 'A1')
    assert store.has_consumed('u1', 'BINANCE', 'IK1', 'A1')

def test_consumption_different_user_allowed(temp_store):
    store = temp_store
    store.register_consumption('u1', 'BINANCE', 'IK2', 'A1')
    assert not store.has_consumed('u2', 'BINANCE', 'IK2', 'A1')

def test_consumption_different_account_allowed(temp_store):
    store = temp_store
    store.register_consumption('u1', 'BINANCE', 'IK3', 'A1')
    assert not store.has_consumed('u1', 'BINANCE', 'IK3', 'A2')

def test_consumption_different_intent_key_allowed(temp_store):
    store = temp_store
    store.register_consumption('u1', 'BINANCE', 'IK4', 'A1')
    assert not store.has_consumed('u1', 'BINANCE', 'IK5', 'A1')

def test_consumption_missing_account_id_uses_no_account(temp_store):
    store = temp_store
    store.register_consumption('u1', 'BINANCE', 'IK6')
    assert store.has_consumed('u1', 'BINANCE', 'IK6', None)
    assert store.has_consumed('u1', 'BINANCE', 'IK6')
    # Otro account_id sí es distinto
    assert not store.has_consumed('u1', 'BINANCE', 'IK6', 'A1')
