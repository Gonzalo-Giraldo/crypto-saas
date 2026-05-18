from __future__ import annotations

from datetime import datetime, timedelta, timezone


DEFAULT_RUNTIME_STALE_TIMEOUT_SECONDS = 60


def is_runtime_heartbeat_stale(
    *,
    runtime_heartbeat_at: datetime | None,
    now: datetime | None = None,
    stale_timeout_seconds: int = DEFAULT_RUNTIME_STALE_TIMEOUT_SECONDS,
) -> bool:
    if runtime_heartbeat_at is None:
        return True

    if stale_timeout_seconds <= 0:
        raise ValueError("stale_timeout_seconds_must_be_positive")

    current_time = now or datetime.now(timezone.utc)

    if runtime_heartbeat_at.tzinfo is None:
        raise ValueError("runtime_heartbeat_at_must_be_timezone_aware")

    if current_time.tzinfo is None:
        raise ValueError("now_must_be_timezone_aware")

    stale_threshold = current_time - timedelta(
        seconds=stale_timeout_seconds,
    )

    return runtime_heartbeat_at < stale_threshold
