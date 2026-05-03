"""
Inert Binance WS worker skeleton.

Import-time guarantees:
- no network
- no WebSocket
- no DB
- no secrets
- no broker actions
- no raw payload logging
"""

from .config import BinanceWsWorkerConfig
from .status import build_worker_status

__all__ = [
    "BinanceWsWorkerConfig",
    "build_worker_status",
]
