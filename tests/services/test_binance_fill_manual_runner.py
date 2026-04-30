import pytest

from apps.api.app.services.binance_fill_manual_runner import run_binance_fill_ingestion_for_intent


def test_runner_matched_no_persist():
    def fetch(symbol, order_id):
        return [
            {"orderId": order_id, "qty": "0.005"},
            {"orderId": order_id, "qty": "0.005"},
        ]

    result = run_binance_fill_ingestion_for_intent(
        db=None,
        intent_id="i1",
        symbol="btcusdt",
        order_id="123",
        execution_ref_type="orderId",
        user_id="u1",
        account_id="default",
        market="SPOT",
        expected_qty="0.01",
        gateway_fetch_trades=fetch,
        persist=False,
    )

    assert result["reason"] == "ok"
    assert result["matched_count"] == 2
    assert result["persisted"] is False
    assert result["reconciliation"]["status"] == "matched"
    assert result["reconciliation"]["safe_for_position_update"] is True


def test_runner_blocks_partial_fill_and_does_not_persist():
    called = {"persist": False}

    def fetch(symbol, order_id):
        return [{"orderId": order_id, "qty": "0.005"}]

    def persist(**kwargs):
        called["persist"] = True

    result = run_binance_fill_ingestion_for_intent(
        db=None,
        intent_id="i1",
        symbol="BTCUSDT",
        order_id="123",
        execution_ref_type="orderId",
        user_id="u1",
        account_id="default",
        market="SPOT",
        expected_qty="0.01",
        gateway_fetch_trades=fetch,
        persist_binance_fills_db=persist,
        persist=True,
    )

    assert result["persisted"] is False
    assert result["reconciliation"]["status"] == "partial"
    assert called["persist"] is False


def test_runner_ignores_unrelated_order_ids_from_symbol_trade_history():
    def fetch(symbol, order_id):
        return [
            {"orderId": order_id, "qty": "0.005"},
            {"orderId": "other", "qty": "9.999"},
            {"orderId": order_id, "qty": "0.005"},
        ]

    result = run_binance_fill_ingestion_for_intent(
        db=None,
        intent_id="i1",
        symbol="BTCUSDT",
        order_id="123",
        execution_ref_type="orderId",
        user_id="u1",
        account_id="default",
        market="SPOT",
        expected_qty="0.01",
        gateway_fetch_trades=fetch,
        persist=False,
    )

    assert result["reason"] == "ok"
    assert result["matched_count"] == 2
    assert result["reconciliation"]["status"] == "matched"
    assert result["reconciliation"]["safe_for_position_update"] is True
    assert all(str(t["orderId"]) == "123" for t in result["trades"])


def test_runner_requires_order_id_execution_ref_type():
    def fetch(symbol, order_id):
        return []

    with pytest.raises(ValueError, match="execution_ref_type_must_be_orderId"):
        run_binance_fill_ingestion_for_intent(
            db=None,
            intent_id="i1",
            symbol="BTCUSDT",
            order_id="123",
            execution_ref_type="clientOrderId",
            user_id="u1",
            account_id="default",
            market="SPOT",
            expected_qty="0.01",
            gateway_fetch_trades=fetch,
            persist=False,
        )
