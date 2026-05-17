from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from apps.api.app.services.auto_pick.binance.market_data import (
    fetch_15m_klines,
    fetch_1h_klines,
    fetch_ticker_24h_rows,
)
from apps.api.app.services.auto_pick.binance.observation_contracts import (
    BinanceMarketObservationSnapshot,
    BinanceMarketReadResult,
)


def _error_code(exc: Exception) -> str:
    message = str(exc).strip()
    return message or exc.__class__.__name__


def _collect_read(
    *,
    source_type: str,
    symbol: str | None,
    interval: str | None,
    fetch: Callable[[], list[Any]],
) -> BinanceMarketReadResult:
    started = time.monotonic()
    try:
        rows = fetch()
    except TimeoutError as exc:
        return BinanceMarketReadResult(
            source_type=source_type,
            symbol=symbol,
            interval=interval,
            status="TIMEOUT",
            rows=[],
            error_code=_error_code(exc),
            latency_ms=int((time.monotonic() - started) * 1000),
        )
    except Exception as exc:
        return BinanceMarketReadResult(
            source_type=source_type,
            symbol=symbol,
            interval=interval,
            status="FETCH_FAILED",
            rows=[],
            error_code=_error_code(exc),
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    status = "OK" if rows else "EMPTY"
    return BinanceMarketReadResult(
        source_type=source_type,
        symbol=symbol,
        interval=interval,
        status=status,
        rows=rows,
        error_code=None,
        latency_ms=int((time.monotonic() - started) * 1000),
    )


def collect_binance_market_observation_snapshot(
    *,
    snapshot_id: str,
    symbols: tuple[str, ...],
) -> BinanceMarketObservationSnapshot:
    """
    Collect immutable Binance market-data evidence for future AWS/data flows.

    This collector is observation-only:
    - no DB writes
    - no scoring
    - no Risk/Intent
    - no execution
    - no mutation of current Auto-pick runtime
    """

    reads: list[BinanceMarketReadResult] = [
        _collect_read(
            source_type="ticker_24h",
            symbol=None,
            interval=None,
            fetch=fetch_ticker_24h_rows,
        )
    ]

    for raw_symbol in symbols:
        symbol = str(raw_symbol or "").upper().strip()
        if not symbol:
            continue

        reads.append(
            _collect_read(
                source_type="klines",
                symbol=symbol,
                interval="1h",
                fetch=lambda symbol=symbol: fetch_1h_klines(symbol),
            )
        )
        reads.append(
            _collect_read(
                source_type="klines",
                symbol=symbol,
                interval="15m",
                fetch=lambda symbol=symbol: fetch_15m_klines(symbol),
            )
        )

    return BinanceMarketObservationSnapshot(
        snapshot_id=snapshot_id,
        broker="BINANCE",
        market="FUTURES",
        reads=tuple(reads),
    )
