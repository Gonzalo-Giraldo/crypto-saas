from __future__ import annotations

import threading


class SchedulerWorkerControl:
    def __init__(
        self,
        *,
        stop_event: threading.Event | None = None,
    ):
        self._stop_event = stop_event or threading.Event()

    @property
    def stop_event(self) -> threading.Event:
        return self._stop_event

    def should_stop(self) -> bool:
        return self._stop_event.is_set()

    def request_stop(self) -> None:
        self._stop_event.set()

    def wait(self, timeout: float) -> bool:
        return self._stop_event.wait(timeout=timeout)
