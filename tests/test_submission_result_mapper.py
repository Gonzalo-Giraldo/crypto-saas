import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from m_order_submission.submission_result_mapper import normalize_runtime_result


def test_failure_result_keeps_error():
    result = {
        "request_id": "r1",
        "order_id": "o1",
        "user_id": "u1",
        "broker": "ibkr",
        "success": False,
        "error": "boom",
    }

    out = normalize_runtime_result(result)

    assert out == {
        "request_id": "r1",
        "order_id": "o1",
        "user_id": "u1",
        "broker": "ibkr",
        "success": False,
        "error": "boom",
    }


def test_success_result_with_broker_order_id():
    result = {
        "request_id": "r2",
        "order_id": "o2",
        "user_id": "u2",
        "broker": "ibkr",
        "success": True,
        "broker_order_id": "b123",
        "status": "Submitted",
        "symbol": "AAPL",
        "side": "BUY",
        "qty": 1.0,
        "order_ref": "o2",
    }

    out = normalize_runtime_result(result)

    assert out == {
        "request_id": "r2",
        "order_id": "o2",
        "user_id": "u2",
        "broker": "ibkr",
        "success": True,
        "broker_order_id": "b123",
        "broker_status": "Submitted",
        "symbol": "AAPL",
        "side": "BUY",
        "qty": 1.0,
        "order_ref": "o2",
    }


def test_success_result_without_broker_order_id_returns_none():
    result = {
        "request_id": "r3",
        "order_id": "o3",
        "user_id": "u3",
        "broker": "ibkr",
        "success": True,
        "status": "Submitted",
        "symbol": "MSFT",
        "side": "SELL",
        "qty": 2.0,
        "order_ref": "o3",
    }

    out = normalize_runtime_result(result)

    assert out["success"] is True
    assert out["broker_order_id"] is None
    assert out["broker_status"] == "Submitted"
    assert out["order_ref"] == "o3"
