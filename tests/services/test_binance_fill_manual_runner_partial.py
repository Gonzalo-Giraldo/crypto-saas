from apps.api.app.services.binance_fill_manual_runner import run_binance_fill_ingestion_for_intent


def _trade(*, trade_id="t1", order_id="100", qty="0.5"):
    return {
        "id": trade_id,
        "orderId": order_id,
        "symbol": "BTCUSDT",
        "qty": qty,
        "price": "100.0",
        "quoteQty": "50.0",
        "commission": "0",
        "commissionAsset": "USDT",
        "time": 1,
        "isBuyer": True,
    }


def test_partial_with_matched_trades_persists_but_reconciliation_is_partial():
    calls = []

    result = run_binance_fill_ingestion_for_intent(
        db=object(),
        intent_id="intent-1",
        symbol="BTCUSDT",
        order_id="100",
        execution_ref_type="orderId",
        user_id="user-1",
        account_id="default",
        market="SPOT",
        expected_qty="1.0",
        gateway_fetch_trades=lambda symbol, order_id: [_trade(qty="0.5")],
        persist_binance_fills_db=lambda **kwargs: calls.append(kwargs) or {"inserted": 1, "skipped": 0},
        persist=True,
    )

    assert result["persisted"] is True
    assert result["matched_count"] == 1
    assert result["reconciliation"]["status"] == "partial"
    assert result["reconciliation"]["safe_for_position_update"] is False
    assert len(calls) == 1


def test_overfilled_with_matched_trades_persists_but_reconciliation_is_overfilled():
    calls = []

    result = run_binance_fill_ingestion_for_intent(
        db=object(),
        intent_id="intent-1",
        symbol="BTCUSDT",
        order_id="100",
        execution_ref_type="orderId",
        user_id="user-1",
        account_id="default",
        market="SPOT",
        expected_qty="1.0",
        gateway_fetch_trades=lambda symbol, order_id: [_trade(qty="1.5")],
        persist_binance_fills_db=lambda **kwargs: calls.append(kwargs) or {"inserted": 1, "skipped": 0},
        persist=True,
    )

    assert result["persisted"] is True
    assert result["matched_count"] == 1
    assert result["reconciliation"]["status"] == "overfilled"
    assert result["reconciliation"]["safe_for_position_update"] is False
    assert len(calls) == 1


def test_no_matching_trades_does_not_persist():
    calls = []

    result = run_binance_fill_ingestion_for_intent(
        db=object(),
        intent_id="intent-1",
        symbol="BTCUSDT",
        order_id="100",
        execution_ref_type="orderId",
        user_id="user-1",
        account_id="default",
        market="SPOT",
        expected_qty="1.0",
        gateway_fetch_trades=lambda symbol, order_id: [_trade(order_id="999")],
        persist_binance_fills_db=lambda **kwargs: calls.append(kwargs) or {"inserted": 1, "skipped": 0},
        persist=True,
    )

    assert result["persisted"] is False
    assert result["matched_count"] == 0
    assert result["reason"] == "no_matching_trades"
    assert calls == []
