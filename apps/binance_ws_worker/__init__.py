"""
Binance WS worker package.

Initial safe skeleton only:
- no network
- no DB
- no secrets read at import time
- no broker actions
- no side effects
"""

__all__ = [
    "BinanceWsWorkerConfig",
    "build_worker_status",
    "main",
]

from apps.binance_ws_worker.config import BinanceWsWorkerConfig
from apps.binance_ws_worker.main import build_worker_status, main
