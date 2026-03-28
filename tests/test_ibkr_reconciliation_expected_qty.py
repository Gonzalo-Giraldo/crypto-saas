import pytest
from types import SimpleNamespace
from apps.api.app.services.ibkr_reconciliation import reconcile_ibkr_fills

def make_fill(qty, price=100, fill_id="F1", symbol="AAPL", user_id="U1", broker="ibkr", execution_ref="E1"):
    return SimpleNamespace(
        fill_id=fill_id,
        symbol=symbol,
        qty=qty,
        price=price,
        timestamp="2026-03-28T00:00:00Z",
        user_id=user_id,
        broker=broker,
        execution_ref=execution_ref
    )

def test_reconcile_no_fills():
    result = reconcile_ibkr_fills([], expected_qty=None)
    assert result["status"] == "not_found"
    result = reconcile_ibkr_fills([], expected_qty=1)
    assert result["status"] == "not_found"

def test_reconcile_filled_without_expected_qty():
    fills = [make_fill(1, 150)]
    result = reconcile_ibkr_fills(fills, expected_qty=None)
    assert result["status"] == "filled"
    assert result["total_qty"] == 1
    assert result["avg_price"] == 150

def test_reconcile_partial_and_filled_with_expected_qty():
    fills = [make_fill(0.5, 100), make_fill(0.4, 200, fill_id="F2")]
    # total_qty = 0.9, expected_qty = 1
    result = reconcile_ibkr_fills(fills, expected_qty=1)
    assert result["status"] == "partial"
    # total_qty = 1.1, expected_qty = 1
    fills2 = [make_fill(0.5, 100), make_fill(0.6, 200, fill_id="F2")]
    result2 = reconcile_ibkr_fills(fills2, expected_qty=1)
    assert result2["status"] == "filled"
    # total_qty = 0, expected_qty = 1
    result3 = reconcile_ibkr_fills([], expected_qty=1)
    assert result3["status"] == "not_found"