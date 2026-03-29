
import pytest
from unittest.mock import MagicMock, patch
from apps.worker.app.engine.execution_runtime import execute_ibkr_test_order_for_user



def _mock_secret(*args, **kwargs):
    return {"exchange": "IBKR", "api_key": "dummy_key", "api_secret": "dummy_secret"}

@pytest.fixture
def fake_db(monkeypatch):
    # Patch SessionLocal to return a MagicMock con execute().fetchone() = None
    with patch("apps.worker.app.engine.execution_runtime.SessionLocal") as session_patch:
        db_mock = MagicMock()
        db_mock.execute.return_value.fetchone.return_value = None
        session_patch.return_value = db_mock
        yield session_patch

def test_ibkr_reconciliation_status_filled(fake_db):
    with patch("apps.worker.app.engine.execution_runtime.get_decrypted_exchange_secret", _mock_secret), \
         patch("apps.worker.app.engine.execution_runtime.send_ibkr_test_order") as send_order_mock, \
         patch("apps.api.app.services.ibkr_reconciliation.get_ibkr_reconciliation_source") as get_source, \
         patch("apps.api.app.services.ibkr_reconciliation.reconcile_ibkr_fills") as reconcile:
        send_order_mock.return_value = {
            "success": True,
            "order_id": "oid-123",
            "status": "Submitted",
            "symbol": "AAPL",
            "side": "BUY",
            "qty": 10,
        }
        get_source.return_value = [MagicMock(qty=10, price=100, fill_id="f1", symbol="AAPL", timestamp=1234567890, user_id="u", broker="ibkr", execution_ref="ref")]
        reconcile.return_value = {"status": "filled", "total_qty": 10, "avg_price": 100, "fills": []}
        resp = execute_ibkr_test_order_for_user(
            user_id="u", symbol="AAPL", side="BUY", qty=10, account_id="acc", intent_key="ik"
        )
        assert resp["reconciliation_status"] == "filled"
        assert resp["execution_complete"] is True
        assert resp["expected_qty"] == 10
        assert resp["filled_qty"] == 10
        assert resp["remaining_qty"] == 0
        assert resp["requires_manual_review"] is False
        assert resp["broker_trade_time"] == 1234567890

def test_ibkr_reconciliation_status_partial(fake_db):

    with patch("apps.worker.app.engine.execution_runtime.get_decrypted_exchange_secret", _mock_secret), \
         patch("apps.worker.app.engine.execution_runtime.send_ibkr_test_order") as send_order_mock, \
         patch("apps.api.app.services.ibkr_reconciliation.get_ibkr_reconciliation_source") as get_source, \
         patch("apps.api.app.services.ibkr_reconciliation.reconcile_ibkr_fills") as reconcile:
        send_order_mock.return_value = {
            "success": True,
            "order_id": "oid-124",
            "status": "Submitted",
            "symbol": "AAPL",
            "side": "BUY",
            "qty": 10,
        }
        get_source.return_value = [MagicMock(qty=5, price=100, fill_id="f1", symbol="AAPL", timestamp=987654321, user_id="u", broker="ibkr", execution_ref="ref")]
        reconcile.return_value = {"status": "partial", "total_qty": 5, "avg_price": 100, "fills": []}
        resp = execute_ibkr_test_order_for_user(
            user_id="u", symbol="AAPL", side="BUY", qty=10, account_id="acc", intent_key="ik"
        )
        assert resp["reconciliation_status"] == "partial"
        assert resp["execution_complete"] is False
        assert resp["expected_qty"] == 10
        assert resp["filled_qty"] == 5
        assert resp["remaining_qty"] == 5
        assert resp["requires_manual_review"] is True
        assert resp["broker_trade_time"] == 987654321

def test_ibkr_reconciliation_status_not_found(fake_db):
    with patch("apps.worker.app.engine.execution_runtime.get_decrypted_exchange_secret", _mock_secret), \
         patch("apps.worker.app.engine.execution_runtime.send_ibkr_test_order") as send_order_mock, \
         patch("apps.api.app.services.ibkr_reconciliation.get_ibkr_reconciliation_source") as get_source, \
         patch("apps.api.app.services.ibkr_reconciliation.reconcile_ibkr_fills") as reconcile:
        send_order_mock.return_value = {
            "success": True,
            "order_id": "oid-125",
            "status": "Submitted",
            "symbol": "AAPL",
            "side": "BUY",
            "qty": 10,
        }
        get_source.return_value = []
        reconcile.return_value = {"status": "not_found", "total_qty": 0, "avg_price": None, "fills": []}
        resp = execute_ibkr_test_order_for_user(
            user_id="u", symbol="AAPL", side="BUY", qty=10, account_id="acc", intent_key="ik"
        )
        assert resp["reconciliation_status"] == "not_found"
        assert resp["execution_complete"] is False
        assert resp["expected_qty"] == 10
        assert resp["filled_qty"] == 0
        assert resp["remaining_qty"] == 10
        assert resp["requires_manual_review"] is False
        assert resp["broker_trade_time"] is None
