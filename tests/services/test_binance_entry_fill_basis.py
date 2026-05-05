import inspect
from dataclasses import dataclass

from apps.worker.app.engine.binance_entry_fill_basis import derive_binance_entry_fill_basis


def test_matched_with_two_valid_fills_calculates_weighted_average():
    result = derive_binance_entry_fill_basis(
        trades=[
            {"qty": "0.4", "price": "100"},
            {"qty": "0.6", "price": "110"},
        ],
        reconciliation_status="matched",
    )

    assert result == {
        "filled_qty": "1.0",
        "avg_entry_price": "106",
        "reconciliation_status": "matched",
        "usable_for_exits": True,
        "reason": "ok",
    }


def test_partial_is_usable_with_real_fill_qty_only():
    result = derive_binance_entry_fill_basis(
        trades=[
            {"qty": "0.5", "price": "200"},
        ],
        reconciliation_status="partial",
    )

    assert result["filled_qty"] == "0.5"
    assert result["avg_entry_price"] == "200"
    assert result["usable_for_exits"] is True
    assert result["reason"] == "ok"


def test_overfilled_is_usable_with_valid_real_fill():
    result = derive_binance_entry_fill_basis(
        trades=[
            {"qty": "1.2", "price": "50"},
        ],
        reconciliation_status="overfilled",
    )

    assert result["filled_qty"] == "1.2"
    assert result["avg_entry_price"] == "50"
    assert result["usable_for_exits"] is True
    assert result["reason"] == "ok"


def test_no_valid_fills_returns_not_usable():
    result = derive_binance_entry_fill_basis(
        trades=[
            {"qty": "0", "price": "100"},
            {"qty": "1", "price": "0"},
            {"qty": "invalid", "price": "100"},
            {"qty": "1", "price": "invalid"},
        ],
        reconciliation_status="matched",
    )

    assert result == {
        "filled_qty": "0",
        "avg_entry_price": "0",
        "reconciliation_status": "matched",
        "usable_for_exits": False,
        "reason": "no_valid_fills",
    }


def test_status_not_usable_returns_not_usable_even_with_valid_fills():
    result = derive_binance_entry_fill_basis(
        trades=[
            {"qty": "1", "price": "100"},
        ],
        reconciliation_status="no_matching_trades",
    )

    assert result["filled_qty"] == "1"
    assert result["avg_entry_price"] == "100"
    assert result["reconciliation_status"] == "no_matching_trades"
    assert result["usable_for_exits"] is False
    assert result["reason"] == "reconciliation_status_not_usable"


def test_signature_does_not_accept_expected_qty_and_partial_uses_real_sum():
    signature = inspect.signature(derive_binance_entry_fill_basis)
    assert "expected_qty" not in signature.parameters

    result = derive_binance_entry_fill_basis(
        trades=[
            {"qty": "0.2", "price": "100"},
            {"qty": "0.3", "price": "100"},
        ],
        reconciliation_status="partial",
    )

    assert result["filled_qty"] == "0.5"
    assert result["avg_entry_price"] == "100"
    assert result["usable_for_exits"] is True


def test_quote_qty_is_not_used_for_average_price():
    result = derive_binance_entry_fill_basis(
        trades=[
            {"qty": "2", "price": "10", "quoteQty": "999999"},
            {"qty": "1", "price": "40", "quoteQty": "1"},
        ],
        reconciliation_status="matched",
    )

    assert result["filled_qty"] == "3"
    assert result["avg_entry_price"] == "20"
    assert result["usable_for_exits"] is True


@dataclass
class TradeLikeObject:
    qty: str
    price: str


def test_supports_simple_attribute_objects():
    result = derive_binance_entry_fill_basis(
        trades=[
            TradeLikeObject(qty="0.25", price="80"),
            TradeLikeObject(qty="0.75", price="120"),
        ],
        reconciliation_status="matched",
    )

    assert result["filled_qty"] == "1.00"
    assert result["avg_entry_price"] == "110"
    assert result["usable_for_exits"] is True
