import pytest

from apps.api.app.services.position_pnl_service import calculate_position_realized_pnl


def test_calculate_position_realized_pnl_long_buy():
    assert calculate_position_realized_pnl(
        side="BUY",
        entry_price=100,
        exit_price=110,
        qty=2,
        fees=1,
    ) == 19


def test_calculate_position_realized_pnl_long_alias():
    assert calculate_position_realized_pnl(
        side="LONG",
        entry_price=100,
        exit_price=90,
        qty=2,
        fees=1,
    ) == -21


def test_calculate_position_realized_pnl_short_sell():
    assert calculate_position_realized_pnl(
        side="SELL",
        entry_price=100,
        exit_price=90,
        qty=2,
        fees=1,
    ) == 19


def test_calculate_position_realized_pnl_short_alias():
    assert calculate_position_realized_pnl(
        side="SHORT",
        entry_price=100,
        exit_price=110,
        qty=2,
        fees=1,
    ) == -21


def test_calculate_position_realized_pnl_rejects_unknown_side():
    with pytest.raises(ValueError, match="unsupported_position_side"):
        calculate_position_realized_pnl(
            side="FLAT",
            entry_price=100,
            exit_price=110,
            qty=1,
        )
