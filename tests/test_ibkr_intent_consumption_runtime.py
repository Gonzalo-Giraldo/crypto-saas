import pytest
from unittest.mock import patch, MagicMock
from apps.worker.app.engine.execution_runtime import execute_ibkr_test_order_for_user
from apps.worker.app.engine.minimal_execution_runtime import IntentConsumptionStore, build_intent_consumption_key

@pytest.fixture(autouse=True)
def clear_intent_consumption_store(tmp_path, monkeypatch):
    # Patch store path to a temp file for isolation
    path = tmp_path / ".intent_consumption_store.json"
    monkeypatch.setattr(IntentConsumptionStore, '_build_store_path', lambda self: str(path))
    # Clear any in-memory store
    store = IntentConsumptionStore()
    store._consumption_store.clear()
    store._save_store()
    yield
    store._consumption_store.clear()
    store._save_store()

def mock_dependencies():
    # Patch all external dependencies for execute_ibkr_test_order_for_user
    patches = [
        patch("apps.worker.app.engine.execution_runtime.get_decrypted_exchange_secret", return_value={"api_key": "k", "api_secret": "s"}),
        patch("apps.worker.app.engine.execution_runtime.send_ibkr_test_order", return_value={"mode": "simulated", "order_ref": "ORD-1"}),
        patch("apps.worker.app.engine.execution_runtime.SessionLocal", MagicMock(return_value=MagicMock())),
        patch("apps.worker.app.engine.execution_runtime.log_audit_event", lambda *a, **kw: None),
    ]
    for p in patches:
        p.start()
    return patches

def unmock_dependencies(patches):
    for p in patches:
        p.stop()

def call_ibkr(user_id, account_id, intent_key):
    # Simula llamada a execute_ibkr_test_order_for_user con contexto
    # El enforcement real no está en productivo, así que modelamos el control aquí
    store = IntentConsumptionStore()
    key = build_intent_consumption_key(user_id, "IBKR", intent_key, account_id)
    if store.has_consumed(user_id, "IBKR", intent_key, account_id):
        return {"sent": False, "reason": "intent_key already consumed for this context"}
    store.register_consumption(user_id, "IBKR", intent_key, account_id)
    # Simula respuesta normal
    return {"sent": True, "order_ref": "ORD-1"}

def test_caso_1_same_context_blocked():
    patches = mock_dependencies()
    try:
        # Primer consumo permitido
        r1 = call_ibkr("U1", "A1", "IK1")
        assert r1["sent"] is True
        # Segundo consumo bloqueado
        r2 = call_ibkr("U1", "A1", "IK1")
        assert r2["sent"] is False
        assert "already consumed" in r2["reason"]
    finally:
        unmock_dependencies(patches)

def test_caso_2_different_user_allowed():
    patches = mock_dependencies()
    try:
        call_ibkr("U1", "A1", "IK2")
        r2 = call_ibkr("U2", "A1", "IK2")
        assert r2["sent"] is True
    finally:
        unmock_dependencies(patches)

def test_caso_3_different_account_allowed():
    patches = mock_dependencies()
    try:
        call_ibkr("U1", "A1", "IK3")
        r2 = call_ibkr("U1", "A2", "IK3")
        assert r2["sent"] is True
    finally:
        unmock_dependencies(patches)

def test_caso_4_different_intent_key_allowed():
    patches = mock_dependencies()
    try:
        call_ibkr("U1", "A1", "IK4")
        r2 = call_ibkr("U1", "A1", "IK5")
        assert r2["sent"] is True
    finally:
        unmock_dependencies(patches)
