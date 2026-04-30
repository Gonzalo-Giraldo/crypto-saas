from decimal import Decimal

import pytest

from apps.api.app.services.binance_derived_position_service import (
    derive_binance_positions_from_fill_rows,
)


def test_derive_open_position_from_single_buy_fill():
    rows = [
        {
            "user_id": "4687a88b-9a84-4277-8fdf-26b5dc7c8096",
            "account_id": "default",
            "broker": "BINANCE",
            "market": "SPOT",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": "0.00010000",
            "quote_qty": "7.83516600",
            "commission_usdt": "0",
        }
    ]

    out = derive_binance_positions_from_fill_rows(rows)

    assert len(out) == 1
    assert out[0]["symbol"] == "BTCUSDT"
    assert out[0]["net_qty"] == Decimal("0.00010000")
    assert out[0]["buy_quote_usdt"] == Decimal("7.83516600")
    assert out[0]["fills_count"] == 1
    assert out[0]["position_status"] == "OPEN"


def test_derive_closed_position_when_buy_equals_sell():
    rows = [
        {
            "user_id": "u1",
            "account_id": "default",
            "broker": "BINANCE",
            "market": "SPOT",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": "0.01",
            "quote_qty": "100",
            "commission_usdt": "1",
        },
        {
            "user_id": "u1",
            "account_id": "default",
            "broker": "BINANCE",
            "market": "SPOT",
            "symbol": "BTCUSDT",
            "side": "SELL",
            "qty": "0.01",
            "quote_qty": "110",
            "commission_usdt": "1.5",
        },
    ]

    out = derive_binance_positions_from_fill_rows(rows)

    assert out[0]["buy_qty"] == Decimal("0.01")
    assert out[0]["sell_qty"] == Decimal("0.01")
    assert out[0]["net_qty"] == Decimal("0.00")
    assert out[0]["buy_quote_usdt"] == Decimal("100")
    assert out[0]["sell_quote_usdt"] == Decimal("110")
    assert out[0]["commission_usdt"] == Decimal("2.5")
    assert out[0]["fills_count"] == 2
    assert out[0]["position_status"] == "CLOSED"


def test_rejects_non_binance_rows():
    with pytest.raises(ValueError, match="broker_must_be_BINANCE"):
        derive_binance_positions_from_fill_rows(
            [
                {
                    "user_id": "u1",
                    "account_id": "default",
                    "broker": "IBKR",
                    "market": "SPOT",
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "qty": "1",
                    "quote_qty": "1",
                    "commission_usdt": "0",
                }
            ]
        )


def test_rejects_invalid_side():
    with pytest.raises(ValueError, match="side_invalid"):
        derive_binance_positions_from_fill_rows(
            [
                {
                    "user_id": "u1",
                    "account_id": "default",
                    "broker": "BINANCE",
                    "market": "SPOT",
                    "symbol": "BTCUSDT",
                    "side": "HOLD",
                    "qty": "1",
                    "quote_qty": "1",
                    "commission_usdt": "0",
                }
            ]
        )
