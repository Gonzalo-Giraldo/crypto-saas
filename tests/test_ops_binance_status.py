import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Importar solo el router, no toda la app
from apps.api.app.api.ops import router

# Montar una app mínima solo con el router de ops
app = FastAPI()
app.include_router(router)
client = TestClient(app)

# Helper para mockear IntentConsumptionStore
class DummyConsumption:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

def make_consumption(**kwargs):
    return DummyConsumption(**kwargs)

@pytest.mark.parametrize("payload,store_return,expected_success,expected_status", [
    # 1. broker != binance
    ({"broker": "ibkr", "broker_execution_id": "abc", "broker_execution_id_type": "client_order_id", "market": "BTCUSDT", "symbol": "BTCUSDT"},
     make_consumption(broker="ibkr", broker_execution_id="abc", broker_execution_id_type="client_order_id", market="BTCUSDT", symbol="BTCUSDT"),
     False, 200),
    # 2. no existe consumption record
    ({"broker": "binance", "broker_execution_id": "abc", "broker_execution_id_type": "client_order_id", "market": "BTCUSDT", "symbol": "BTCUSDT"},
     None,
     False, 200),
    # 3. falta broker_execution_id
    ({"broker": "binance", "broker_execution_id": None, "broker_execution_id_type": "client_order_id", "market": "BTCUSDT", "symbol": "BTCUSDT"},
     make_consumption(broker="binance", broker_execution_id=None, broker_execution_id_type="client_order_id", market="BTCUSDT", symbol="BTCUSDT"),
     False, 200),
    # 4. falta broker_execution_id_type
    ({"broker": "binance", "broker_execution_id": "abc", "broker_execution_id_type": None, "market": "BTCUSDT", "symbol": "BTCUSDT"},
     make_consumption(broker="binance", broker_execution_id="abc", broker_execution_id_type=None, market="BTCUSDT", symbol="BTCUSDT"),
     False, 200),
    # 5. falta market interno
    ({"broker": "binance", "broker_execution_id": "abc", "broker_execution_id_type": "client_order_id", "market": None, "symbol": "BTCUSDT"},
     make_consumption(broker="binance", broker_execution_id="abc", broker_execution_id_type="client_order_id", market=None, symbol="BTCUSDT"),
     False, 200),
    # 6. falta symbol interno
    ({"broker": "binance", "broker_execution_id": "abc", "broker_execution_id_type": "client_order_id", "market": "BTCUSDT", "symbol": None},
     make_consumption(broker="binance", broker_execution_id="abc", broker_execution_id_type="client_order_id", market="BTCUSDT", symbol=None),
     False, 200),
])
def test_binance_status_failures(payload, store_return, expected_success, expected_status):
    with patch("apps.api.app.api.ops.IntentConsumptionStore") as mock_store, \
         patch("apps.api.app.api.ops.get_decrypted_exchange_secret", return_value={}), \
         patch("apps.api.app.api.ops.binance_query_order_status") as mock_query:
        mock_store.return_value.get_by_broker_execution_id.return_value = store_return
        response = client.get("/intent-binance-status", params=payload)
        data = response.json()
        assert response.status_code == expected_status
        assert data["success"] is expected_success
        assert not mock_query.called


def test_binance_status_success():
    payload = {
        "broker": "binance",
        "broker_execution_id": "abc",
        "broker_execution_id_type": "client_order_id",
        "market": "BTCUSDT",
        "symbol": "BTCUSDT"
    }
    consumption = DummyConsumption(
        broker="binance",
        broker_execution_id="abc",
        broker_execution_id_type="client_order_id",
        market="BTCUSDT",
        symbol="BTCUSDT"
    )
    with patch("apps.api.app.api.ops.IntentConsumptionStore") as mock_store, \
         patch("apps.api.app.api.ops.get_decrypted_exchange_secret", return_value={}), \
         patch("apps.api.app.api.ops.binance_query_order_status", return_value={"status": "ok"}) as mock_query:
        mock_store.return_value.get_by_broker_execution_id.return_value = consumption
        response = client.get("/intent-binance-status", params=payload)
        data = response.json()
        assert response.status_code == 200
        assert data["success"] is True
        mock_query.assert_called_once_with(
            orig_client_order_id="abc",
            market="BTCUSDT",
            symbol="BTCUSDT",
            exchange_secrets={},
        )


# --- NEW TEST: /intent-binance-trades persistence contract ---
def test_intent_binance_trades_persistence_contract():
    """
    Validates that /intent-binance-trades only persists fills when all trades are matched,
    and blocks persistence with explicit reason when trades_contains_unmatched is True.
    """
    payload = {
        "intent_key": "ik1",
        "user_id": "u1",
        "broker": "binance",
        "account_id": "a1"
    }
    # Case 1: All trades matched (should persist)
    trades = [
        {"id": 1, "orderId": "abc", "clientOrderId": "cid", "some": "data"},
        {"id": 2, "orderId": "abc", "clientOrderId": "cid", "some": "data2"}
    ]
    consumption = DummyConsumption(
        broker="binance",
        broker_execution_id="abc",
        broker_execution_id_type="orderId",
        market="BTCUSDT",
        symbol="BTCUSDT"
    )
    with patch("apps.api.app.api.ops.intent_consumption_store") as mock_store, \
         patch("apps.api.app.services.exchange_secrets.get_decrypted_exchange_secret", return_value={"api_key": "k", "api_secret": "s"}), \
         patch("apps.api.app.api.ops.fetch_binance_trades_via_gateway", return_value=trades), \
         patch("apps.api.app.services.binance_fill_db.persist_binance_fills_db", return_value={"persisted": True}) as mock_persist:
        mock_store.get_consumption_record.return_value = {"found": True, "broker_execution_id": "abc", "broker_execution_id_type": "orderId", "symbol": "BTCUSDT", "market": "BTCUSDT"}
        response = client.get("/ops/intent-binance-trades", params=payload)
        print("DEBUG status_code:", response.status_code)
        try:
            print("DEBUG json:", response.json())
        except Exception as e:
            print("DEBUG json error:", str(e))
            print("DEBUG raw response:", response.text)
        data = response.json()
        assert response.status_code == 200
        assert data["db_persistence"]["persisted"] is True
        assert data["trades_contains_unmatched"] is False
        mock_persist.assert_called_once()

        # Case 2: trades_contains_unmatched = True (should block persistence)
        trades_mixed = [
        {"id": 1, "orderId": "abc", "clientOrderId": "cid", "some": "data"},
        {"id": 2, "orderId": "other", "clientOrderId": "cid", "some": "data2"}
    ]
        with patch("apps.api.app.api.ops.intent_consumption_store") as mock_store, \
             patch("apps.api.app.services.exchange_secrets.get_decrypted_exchange_secret", return_value={"api_key": "k", "api_secret": "s"}), \
             patch("apps.api.app.api.ops.fetch_binance_trades_via_gateway", return_value=trades_mixed), \
             patch("apps.api.app.services.binance_fill_db.persist_binance_fills_db") as mock_persist:
            mock_store.get_consumption_record.return_value = {"found": True, "broker_execution_id": "abc", "broker_execution_id_type": "orderId", "symbol": "BTCUSDT", "market": "BTCUSDT"}
            response = client.get("/ops/intent-binance-trades", params=payload)
            data = response.json()
            assert response.status_code == 200
            assert data["db_persistence"]["persisted"] is False
            assert "trades_contains_unmatched" in data["db_persistence"]["reason"]
            assert data["trades_contains_unmatched"] is True
            mock_persist.assert_not_called()
