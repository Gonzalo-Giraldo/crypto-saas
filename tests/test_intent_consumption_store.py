import os
import tempfile
import shutil
import pytest
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
