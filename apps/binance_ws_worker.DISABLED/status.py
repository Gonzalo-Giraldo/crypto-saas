from typing import Any

from .config import BinanceWsWorkerConfig


def build_worker_status(config: BinanceWsWorkerConfig | None = None) -> dict[str, Any]:
    cfg = config or BinanceWsWorkerConfig()
    cfg.validate()

    return {
        "worker_name": cfg.worker_name,
        "mode": cfg.mode,
        "network_enabled": False,
        "db_writes_enabled": False,
        "orders_enabled": False,
        "broker_actions_enabled": False,
        "persistence_enabled": False,
    }
