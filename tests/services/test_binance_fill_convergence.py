from apps.api.app.services.binance_fill_manual_runner import run_binance_fill_ingestion_for_intent


def _trade(*, trade_id, order_id, qty):
    return {
        "id": trade_id,
        "orderId": order_id,
        "symbol": "BTCUSDT",
        "qty": qty,
        "price": "100.0",
        "quoteQty": "100.0",
        "commission": "0",
        "commissionAsset": "USDT",
        "time": 1,
        "isBuyer": True,
    }


def test_partial_then_complete_convergence():
    calls = []

    # Primera ejecución: partial (0.4 de 1.0)
    result_partial = run_binance_fill_ingestion_for_intent(
        db=object(),
        intent_id="intent-1",
        symbol="BTCUSDT",
        order_id="100",
        execution_ref_type="orderId",
        user_id="user-1",
        account_id="default",
        market="SPOT",
        expected_qty="1.0",
        gateway_fetch_trades=lambda symbol, order_id: [
            _trade(trade_id="t1", order_id="100", qty="0.4")
        ],
        persist_binance_fills_db=lambda **kwargs: calls.append(("partial", kwargs)) or {"inserted": 1, "skipped": 0},
        persist=True,
    )

    assert result_partial["persisted"] is True
    assert result_partial["reconciliation"]["status"] == "partial"

    # Segunda ejecución: ahora completa (0.4 + 0.6)
    result_complete = run_binance_fill_ingestion_for_intent(
        db=object(),
        intent_id="intent-1",
        symbol="BTCUSDT",
        order_id="100",
        execution_ref_type="orderId",
        user_id="user-1",
        account_id="default",
        market="SPOT",
        expected_qty="1.0",
        gateway_fetch_trades=lambda symbol, order_id: [
            _trade(trade_id="t1", order_id="100", qty="0.4"),
            _trade(trade_id="t2", order_id="100", qty="0.6"),
        ],
        persist_binance_fills_db=lambda **kwargs: calls.append(("complete", kwargs)) or {"inserted": 1, "skipped": 1},
        persist=True,
    )

    assert result_complete["persisted"] is True
    assert result_complete["reconciliation"]["status"] == "matched"
    assert result_complete["reconciliation"]["safe_for_position_update"] is True

    # Validar que hubo dos persistencias (partial + complete)
    assert len(calls) == 2
