from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from apps.api.app.services.auto_pick.binance.observation_contracts import (
    BinanceMarketReadResult,
    BinanceMarketObservationSnapshot,
)


def test_market_read_result_is_immutable_and_classifies_source():
    row = BinanceMarketReadResult(
        source_type="ticker_24h",
        symbol=None,
        interval=None,
        status="OK",
        rows=[{"symbol": "BTCUSDT"}],
        error_code=None,
        latency_ms=12,
    )

    assert row.source_type == "ticker_24h"
    assert row.status == "OK"
    assert row.row_count == 1

    with pytest.raises(FrozenInstanceError):
        row.status = "FAILED"


def test_observation_snapshot_is_immutable_and_groups_reads():
    ticker = BinanceMarketReadResult(
        source_type="ticker_24h",
        symbol=None,
        interval=None,
        status="OK",
        rows=[{"symbol": "BTCUSDT"}],
        error_code=None,
        latency_ms=10,
    )

    snapshot = BinanceMarketObservationSnapshot(
        snapshot_id="snapshot-1",
        broker="BINANCE",
        market="FUTURES",
        reads=(ticker,),
    )

    assert snapshot.snapshot_id == "snapshot-1"
    assert snapshot.broker == "BINANCE"
    assert snapshot.market == "FUTURES"
    assert snapshot.read_count == 1
    assert snapshot.has_failures is False

    with pytest.raises(FrozenInstanceError):
        snapshot.broker = "IBKR"


def test_observation_snapshot_detects_failures():
    failed = BinanceMarketReadResult(
        source_type="klines",
        symbol="BTCUSDT",
        interval="1h",
        status="FETCH_FAILED",
        rows=[],
        error_code="binance_gateway_request_failed",
        latency_ms=15000,
    )

    snapshot = BinanceMarketObservationSnapshot(
        snapshot_id="snapshot-2",
        broker="BINANCE",
        market="FUTURES",
        reads=(failed,),
    )

    assert snapshot.read_count == 1
    assert snapshot.has_failures is True
