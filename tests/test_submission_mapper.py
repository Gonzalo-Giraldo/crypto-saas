import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest
from m_order_submission.submission_mapper import build_runtime_command


def test_build_runtime_command_complete():
    payload = {
        "user_id": "u1",
        "broker": "ibkr",
        "request_id": "r1",
        "order_id": "o1",
        "symbol": "AAPL",
        "side": "BUY",
        "qty": 1,
        "order_ref": "REF1",
    }

    cmd = build_runtime_command(payload)

    assert cmd == {
        "request_id": "r1",
        "symbol": "AAPL",
        "side": "BUY",
        "qty": 1.0,
        "order_ref": "REF1",
        "user_id": "u1",
        "order_id": "o1",
        "broker": "ibkr",
    }


def test_build_runtime_command_derives_order_ref_from_order_id():
    payload = {
        "user_id": "u2",
        "broker": "ibkr",
        "request_id": "r2",
        "order_id": "o2",
        "symbol": "MSFT",
        "side": "SELL",
        "qty": 2,
    }

    cmd = build_runtime_command(payload)

    assert cmd["order_ref"] == "o2"
    assert cmd["order_id"] == "o2"
    assert cmd["qty"] == 2.0


def test_build_runtime_command_invalid_submission_contract():
    payload = {
        "user_id": "u1",
        "broker": "ibkr",
        "request_id": "r1",
        "order_id": "o1",
        "symbol": "AAPL",
        "side": "BUY",
        "qty": 0,
    }

    with pytest.raises(Exception):
        build_runtime_command(payload)
