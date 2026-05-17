from __future__ import annotations

from apps.api.app.services.auto_pick.binance.observation_collector import (
    collect_binance_market_observation_snapshot,
)


def test_collects_successful_ticker_and_klines_snapshot(monkeypatch):
    import apps.api.app.services.auto_pick.binance.observation_collector as collector

    monkeypatch.setattr(
        collector,
        "fetch_ticker_24h_rows",
        lambda: [{"symbol": "BTCUSDT", "lastPrice": "100"}],
    )
    monkeypatch.setattr(
        collector,
        "fetch_1h_klines",
        lambda symbol: [["0", "1", "2", "1", "1.5", "10"]],
    )
    monkeypatch.setattr(
        collector,
        "fetch_15m_klines",
        lambda symbol: [["0", "1", "2", "1", "1.5", "10"]],
    )

    snapshot = collect_binance_market_observation_snapshot(
        snapshot_id="snapshot-1",
        symbols=("BTCUSDT",),
    )

    assert snapshot.snapshot_id == "snapshot-1"
    assert snapshot.broker == "BINANCE"
    assert snapshot.market == "FUTURES"
    assert snapshot.read_count == 3
    assert snapshot.has_failures is False

    assert [read.source_type for read in snapshot.reads] == [
        "ticker_24h",
        "klines",
        "klines",
    ]
    assert [read.interval for read in snapshot.reads] == [
        None,
        "1h",
        "15m",
    ]


def test_collects_empty_as_explicit_empty_status(monkeypatch):
    import apps.api.app.services.auto_pick.binance.observation_collector as collector

    monkeypatch.setattr(collector, "fetch_ticker_24h_rows", lambda: [])
    monkeypatch.setattr(collector, "fetch_1h_klines", lambda symbol: [])
    monkeypatch.setattr(collector, "fetch_15m_klines", lambda symbol: [])

    snapshot = collect_binance_market_observation_snapshot(
        snapshot_id="snapshot-2",
        symbols=("BTCUSDT",),
    )

    assert snapshot.read_count == 3
    assert snapshot.has_failures is True
    assert [read.status for read in snapshot.reads] == ["EMPTY", "EMPTY", "EMPTY"]


def test_collects_fetch_exception_as_fetch_failed(monkeypatch):
    import apps.api.app.services.auto_pick.binance.observation_collector as collector

    def boom():
        raise RuntimeError("gateway_down")

    monkeypatch.setattr(collector, "fetch_ticker_24h_rows", boom)
    monkeypatch.setattr(collector, "fetch_1h_klines", lambda symbol: [])
    monkeypatch.setattr(collector, "fetch_15m_klines", lambda symbol: [])

    snapshot = collect_binance_market_observation_snapshot(
        snapshot_id="snapshot-3",
        symbols=("BTCUSDT",),
    )

    assert snapshot.reads[0].source_type == "ticker_24h"
    assert snapshot.reads[0].status == "FETCH_FAILED"
    assert snapshot.reads[0].error_code == "gateway_down"
    assert snapshot.has_failures is True
