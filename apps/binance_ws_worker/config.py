from dataclasses import dataclass


@dataclass(frozen=True)
class BinanceWsWorkerConfig:
    worker_name: str = "binance_ws_worker"
    mode: str = "skeleton"

    def validate(self) -> None:
        if self.mode != "skeleton":
            raise ValueError("mode must be 'skeleton'")
