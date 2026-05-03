from dataclasses import dataclass


@dataclass(frozen=True)
class BinanceWsWorkerConfig:
    worker_name: str = "binance_ws_worker"
    mode: str = "dry-run"
    live_enabled: bool = False

    def validate(self) -> None:
        if self.mode not in {"dry-run", "live"}:
            raise ValueError("mode must be 'dry-run' or 'live'")

        if self.mode == "live" and not self.live_enabled:
            raise RuntimeError("live mode requires explicit live_enabled=True")
