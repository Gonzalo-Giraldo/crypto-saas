import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from m_order_lifecycle.pnl_service import build_pnl_for_order

def test_build_pnl_for_sell_order_fifo():
    order = {
        "user_id": "u1",
        "broker": "ibkr",
        "order_id": "sell-1",
        "symbol": "AAPL",
        "side": "SELL",
    }

    executions = [
        {
            "user_id": "u1",
            "broker": "ibkr",
            "order_id": "buy-1",
            "exec_id": "b1",
            "executed_at_precise": "2026-04-01T09:00:00.001",
            "symbol": "AAPL",
            "side": "BUY",
            "qty": 10,
            "price": 100,
            "commission": 1.0,
            "raw_status": "Filled",
            "normalized_status": "filled",
        },
        {
            "user_id": "u1",
            "broker": "ibkr",
            "order_id": "buy-2",
            "exec_id": "b2",
            "executed_at_precise": "2026-04-01T09:05:00.001",
            "symbol": "AAPL",
            "side": "BUY",
            "qty": 16,
            "price": 110,
            "commission": 1.6,
            "raw_status": "Filled",
            "normalized_status": "filled",
        },
        {
            "user_id": "u1",
            "broker": "ibkr",
            "order_id": "sell-1",
            "exec_id": "s1",
            "executed_at_precise": "2026-04-01T09:10:00.001",
            "symbol": "AAPL",
            "side": "SELL",
            "qty": 6,
            "price": 130,
            "commission": 0.6,
            "raw_status": "Filled",
            "normalized_status": "filled",
        },
    ]

    res = build_pnl_for_order(order, executions)

    assert res["order_id"] == "sell-1"
    assert res["gross_pnl"] == 180
    assert round(res["total_commission"], 6) == round(1.0 * 6 / 10 + 0.6, 6)
    assert round(res["net_pnl"], 6) == round(180 - (1.0 * 6 / 10 + 0.6), 6)
    assert res["complete"] is True
    assert res["fifo_source_orders"] == ["buy-1"]
    assert len([m for m in res["fifo_matches"] if m.get("matched_qty", 0) > 0]) == 1
