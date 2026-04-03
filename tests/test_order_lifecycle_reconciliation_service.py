import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from m_order_lifecycle.reconciliation_service import build_reconciliation_for_order


def test_reconciliation_complete_order():
    order = {
        "user_id": "u1",
        "broker": "ibkr",
        "order_id": "o1",
        "symbol": "AAPL",
        "side": "BUY",
        "qty_requested": 10,
    }

    executions = [
        {
            "user_id": "u1",
            "broker": "ibkr",
            "order_id": "o1",
            "exec_id": "e1",
            "executed_at_precise": "2026-04-01T10:00:00.001",
            "symbol": "AAPL",
            "side": "BUY",
            "qty": 5,
            "price": 100,
            "commission": 0.5,
        },
        {
            "user_id": "u1",
            "broker": "ibkr",
            "order_id": "o1",
            "exec_id": "e2",
            "executed_at_precise": "2026-04-01T10:01:00.001",
            "symbol": "AAPL",
            "side": "BUY",
            "qty": 5,
            "price": 110,
            "commission": 0.5,
        },
    ]

    res = build_reconciliation_for_order(order, executions)

    assert res["order_id"] == "o1"
    assert res["qty_executed_total"] == 10
    assert res["reconciliation_status"] == "reconciled"
    assert res["fill_count"] == 2
    assert res["total_commission"] == 1.0
    assert res["avg_execution_price"] == 105


def test_reconciliation_failed_order():
    order = {
        "user_id": "u1",
        "broker": "ibkr",
        "order_id": "o2",
        "symbol": "AAPL",
        "side": "BUY",
        "qty_requested": 10,
    }

    executions = [
        {
            "user_id": "u1",
            "broker": "ibkr",
            "order_id": "o2",
            "exec_id": "e1",
            "executed_at_precise": "2026-04-01T10:00:00.001",
            "symbol": "AAPL",
            "side": "BUY",
            "qty": 0,
            "price": 0,
            "commission": 0,
        },
    ]

    res = build_reconciliation_for_order(order, executions)

    assert res["qty_executed_total"] == 0
    assert res["reconciliation_status"] == "failed"
