import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest
from m_order_submission.submission_contract import (
    validate_submission_payload,
    SubmissionContractError,
)


def test_valid_payload():
    payload = {
        "user_id": "u1",
        "broker": "ibkr",
        "request_id": "r1",
        "order_id": "o1",
        "symbol": "AAPL",
        "side": "BUY",
        "qty": 1,
    }
    assert validate_submission_payload(payload) is True


def test_missing_field():
    payload = {
        "user_id": "u1",
        "broker": "ibkr",
        "request_id": "r1",
        "order_id": "o1",
        "symbol": "AAPL",
        "side": "BUY",
    }
    with pytest.raises(SubmissionContractError):
        validate_submission_payload(payload)


def test_invalid_side():
    payload = {
        "user_id": "u1",
        "broker": "ibkr",
        "request_id": "r1",
        "order_id": "o1",
        "symbol": "AAPL",
        "side": "HOLD",
        "qty": 1,
    }
    with pytest.raises(SubmissionContractError):
        validate_submission_payload(payload)


def test_invalid_qty_zero_message():
    payload = {
        "user_id": "u1",
        "broker": "ibkr",
        "request_id": "r1",
        "order_id": "o1",
        "symbol": "AAPL",
        "side": "BUY",
        "qty": 0,
    }
    with pytest.raises(SubmissionContractError, match="qty must be positive"):
        validate_submission_payload(payload)


def test_non_numeric_qty_message():
    payload = {
        "user_id": "u1",
        "broker": "ibkr",
        "request_id": "r1",
        "order_id": "o1",
        "symbol": "AAPL",
        "side": "BUY",
        "qty": "foo",
    }
    with pytest.raises(SubmissionContractError, match="qty must be a number"):
        validate_submission_payload(payload)
