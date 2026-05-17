from __future__ import annotations

from apps.api.app.services.auto_pick.binance.observation_contracts import (
    BinanceMarketObservationSnapshot,
    BinanceMarketReadResult,
)
from apps.api.app.services.auto_pick.binance.snapshot_runtime import (
    extract_snapshot_market_context,
)


def test_extracts_ticker_and_klines_from_snapshot():
    snapshot = BinanceMarketObservationSnapshot(
        snapshot_id="snapshot-1",
        broker="BINANCE",
        market="FUTURES",
        reads=(
            BinanceMarketReadResult(
                source_type="ticker_24h",
                symbol=None,
                interval=None,
                status="OK",
                rows=[
                    {
                        "symbol": "BTCUSDT",
                        "bidPrice": "100",
                        "askPrice": "101",
                    }
                ],
                error_code=None,
                latency_ms=10,
            ),
            BinanceMarketReadResult(
                source_type="klines",
                symbol="BTCUSDT",
                interval="1h",
                status="OK",
                rows=[
                    ["0", "100", "105", "99", "104", "1000"],
                ],
                error_code=None,
                latency_ms=12,
            ),
            BinanceMarketReadResult(
                source_type="klines",
                symbol="BTCUSDT",
                interval="15m",
                status="OK",
                rows=[
                    ["0", "104", "106", "103", "105", "800"],
                ],
                error_code=None,
                latency_ms=9,
            ),
        ),
    )

    context = extract_snapshot_market_context(snapshot)

    assert context["ticker_rows"][0]["symbol"] == "BTCUSDT"

    assert context["klines_1h"]["BTCUSDT"][0][4] == "104"
    assert context["klines_15m"]["BTCUSDT"][0][4] == "105"


def test_snapshot_context_ignores_failed_reads():
    snapshot = BinanceMarketObservationSnapshot(
        snapshot_id="snapshot-2",
        broker="BINANCE",
        market="FUTURES",
        reads=(
            BinanceMarketReadResult(
                source_type="ticker_24h",
                symbol=None,
                interval=None,
                status="FETCH_FAILED",
                rows=[],
                error_code="gateway_down",
                latency_ms=1000,
            ),
        ),
    )

    context = extract_snapshot_market_context(snapshot)

    assert context["ticker_rows"] == []
    assert context["klines_1h"] == {}
    assert context["klines_15m"] == {}
