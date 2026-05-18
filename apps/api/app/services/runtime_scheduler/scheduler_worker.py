from __future__ import annotations

import time

from apps.api.app.main import (
    _auto_pick_tick_once,
)
from apps.api.app.services.runtime_scheduler.worker_control import (
    SchedulerWorkerControl,
)


def run_scheduler_worker_forever(
    *,
    interval_seconds: float,
    control: SchedulerWorkerControl | None = None,
):
    worker_control = control or SchedulerWorkerControl()

    while not worker_control.should_stop():
        started_at = time.monotonic()

        _auto_pick_tick_once()

        elapsed = time.monotonic() - started_at
        remaining = max(interval_seconds - elapsed, 0.0)

        worker_control.wait(remaining)
