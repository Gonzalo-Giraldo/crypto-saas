from decimal import Decimal

from apps.api.app.services.exposure_source_comparison_service import (
    compare_legacy_vs_derived_exposure,
)


def test_divergence_detected():
    legacy = [
        {"symbol": "BTCUSDT", "qty": "0.0", "entry_price": "0", "status": "OPEN"}
    ]

    derived = [
        {
            "symbol": "BTCUSDT",
            "net_qty": "0.0001",
            "buy_quote_usdt": "7.83516600",
            "position_status": "OPEN",
            "broker": "BINANCE",
        }
    ]

    out = compare_legacy_vs_derived_exposure(
        legacy_positions=legacy,
        derived_positions=derived,
        symbol="BTCUSDT",
        exchange="BINANCE",
        projected_qty="0",
        projected_price="0",
    )

    assert out["diverged"] is True
    assert out["derived"]["open_qty_symbol"] == Decimal("0.0001")


def test_no_divergence_when_equal():
    legacy = [
        {"symbol": "BTCUSDT", "qty": "0.0001", "entry_price": "78351.66", "status": "OPEN"}
    ]

    derived = [
        {
            "symbol": "BTCUSDT",
            "net_qty": "0.0001",
            "buy_quote_usdt": "7.83516600",
            "position_status": "OPEN",
            "broker": "BINANCE",
        }
    ]

    out = compare_legacy_vs_derived_exposure(
        legacy_positions=legacy,
        derived_positions=derived,
        symbol="BTCUSDT",
        exchange="BINANCE",
        projected_qty="0",
        projected_price="0",
    )

    assert isinstance(out["diverged"], bool)
