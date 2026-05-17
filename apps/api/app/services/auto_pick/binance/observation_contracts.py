from __future__ import annotations

import hashlib
import json
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

    @property
    def partial_failure_count(self) -> int:
        return sum(1 for read in self.reads if read.status != "OK")

    @property
    def snapshot_hash(self) -> str:
        economic_reads = [
            {
                "source_type": read.source_type,
                "symbol": read.symbol,
                "interval": read.interval,
                "status": read.status,
                "rows": read.rows,
                "error_code": read.error_code,
            }
            for read in self.reads
        ]
        payload = {
            "broker": self.broker,
            "market": self.market,
            "reads": sorted(
                economic_reads,
                key=lambda item: (
                    str(item["source_type"] or ""),
                    str(item["symbol"] or ""),
                    str(item["interval"] or ""),
                    str(item["status"] or ""),
                    json.dumps(item["rows"], sort_keys=True, separators=(",", ":"), default=str),
                    str(item["error_code"] or ""),
                ),
            ),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
