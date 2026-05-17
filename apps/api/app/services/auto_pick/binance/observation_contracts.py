from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


MarketReadSourceType = Literal[
    "ticker_24h",
    "klines",
]

MarketReadStatus = Literal[
    "OK",
    "EMPTY",
    "FETCH_FAILED",
    "INVALID_PAYLOAD",
    "TIMEOUT",
]


@dataclass(frozen=True)
class BinanceMarketReadResult:
    """
    Immutable Binance market-data read evidence.

    This contract is observation-only:
    - no DB writes
    - no trading decision
    - no Risk/Intent coupling
    - no broker mutation
    """

    source_type: MarketReadSourceType
    symbol: str | None
    interval: str | None
    status: MarketReadStatus
    rows: list[Any] = field(default_factory=list)
    error_code: str | None = None
    latency_ms: int | None = None

    @property
    def row_count(self) -> int:
        return len(self.rows)


@dataclass(frozen=True)
class BinanceMarketObservationSnapshot:
    """
    Immutable grouped market-data snapshot for deterministic Auto-pick evaluation.

    The snapshot is a boundary object for AWS/data collection work. It must remain
    independent from production DB state, Risk, Intent, and Execution.
    """

    snapshot_id: str
    broker: str
    market: str
    reads: tuple[BinanceMarketReadResult, ...]

    @property
    def read_count(self) -> int:
        return len(self.reads)

    @property
    def has_failures(self) -> bool:
        return any(read.status != "OK" for read in self.reads)
