from dataclasses import dataclass


ALLOWED_WORKER_MODES = frozenset({"skeleton", "dry-run"})


@dataclass(frozen=True)
class BinanceWsWorkerConfig:
    worker_name: str = "binance_ws_worker"
    mode: str = "skeleton"

    def validate(self) -> None:
        if self.mode not in ALLOWED_WORKER_MODES:
            raise ValueError("mode must be one of: dry-run, skeleton")
