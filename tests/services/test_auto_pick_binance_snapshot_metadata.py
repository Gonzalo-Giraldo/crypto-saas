from __future__ import annotations

from apps.api.app.services.auto_pick.binance.observation_contracts import (
    BinanceMarketObservationSnapshot,
    BinanceMarketReadResult,
)


def _snapshot(reads):
    return BinanceMarketObservationSnapshot(
        snapshot_id="snapshot-meta",
        broker="BINANCE",
        market="FUTURES",
        reads=tuple(reads),
    )


def test_snapshot_reports_partial_failure_count():
    snapshot = _snapshot(
        (
            BinanceMarketReadResult(
                source_type="ticker_24h",
                symbol=None,
                interval=None,
                status="OK",
                rows=[{"symbol": "BTCUSDT"}],
                error_code=None,
                latency_ms=10,
            ),
            BinanceMarketReadResult(
                source_type="klines",
                symbol="BTCUSDT",
                interval="1h",
                status="FETCH_FAILED",
                rows=[],
                error_code="gateway_down",
                latency_ms=1000,
            ),
        )
    )

    assert snapshot.partial_failure_count == 1


def test_snapshot_hash_is_stable_for_same_economic_content():
    read_a = BinanceMarketReadResult(
        source_type="ticker_24h",
        symbol=None,
        interval=None,
        status="OK",
        rows=[{"symbol": "BTCUSDT", "lastPrice": "100"}],
        error_code=None,
        latency_ms=10,
    )

    read_b = BinanceMarketReadResult(
        source_type="klines",
        symbol="BTCUSDT",
        interval="1h",
        status="OK",
        rows=[["0", "1", "2", "1", "1.5", "10"]],
        error_code=None,
        latency_ms=99999,
    )

    snapshot_a = _snapshot((read_a, read_b))
    snapshot_b = _snapshot((read_b, read_a))

    assert snapshot_a.snapshot_hash == snapshot_b.snapshot_hash


def test_snapshot_hash_changes_when_market_content_changes():
    snapshot_a = _snapshot(
        (
            BinanceMarketReadResult(
                source_type="ticker_24h",
                symbol=None,
                interval=None,
                status="OK",
                rows=[{"symbol": "BTCUSDT", "lastPrice": "100"}],
                error_code=None,
                latency_ms=10,
            ),
        )
    )

    snapshot_b = _snapshot(
        (
            BinanceMarketReadResult(
                source_type="ticker_24h",
                symbol=None,
                interval=None,
                status="OK",
                rows=[{"symbol": "BTCUSDT", "lastPrice": "101"}],
                error_code=None,
                latency_ms=10,
            ),
        )
    )

    assert snapshot_a.snapshot_hash != snapshot_b.snapshot_hash
