from datetime import datetime, timedelta, timezone

from apps.api.app.services.runtime_scheduler.runtime_stale_evaluator import (
    DEFAULT_RUNTIME_STALE_TIMEOUT_SECONDS,
    is_runtime_heartbeat_stale,
)


def test_none_heartbeat_is_stale_fail_closed():
    now = datetime.now(timezone.utc)

    result = is_runtime_heartbeat_stale(
        runtime_heartbeat_at=None,
        now=now,
    )

    assert result is True


def test_recent_heartbeat_is_not_stale():
    now = datetime.now(timezone.utc)

    heartbeat = now - timedelta(seconds=10)

    result = is_runtime_heartbeat_stale(
        runtime_heartbeat_at=heartbeat,
        now=now,
        stale_timeout_seconds=60,
    )

    assert result is False


def test_old_heartbeat_is_stale():
    now = datetime.now(timezone.utc)

    heartbeat = now - timedelta(seconds=120)

    result = is_runtime_heartbeat_stale(
        runtime_heartbeat_at=heartbeat,
        now=now,
        stale_timeout_seconds=60,
    )

    assert result is True


def test_exact_threshold_boundary_is_not_stale():
    now = datetime.now(timezone.utc)

    heartbeat = now - timedelta(seconds=60)

    result = is_runtime_heartbeat_stale(
        runtime_heartbeat_at=heartbeat,
        now=now,
        stale_timeout_seconds=60,
    )

    assert result is False


def test_runtime_heartbeat_must_be_timezone_aware():
    naive_heartbeat = datetime.utcnow()

    try:
        is_runtime_heartbeat_stale(
            runtime_heartbeat_at=naive_heartbeat,
            now=datetime.now(timezone.utc),
        )
    except ValueError as exc:
        assert str(exc) == "runtime_heartbeat_at_must_be_timezone_aware"
    else:
        raise AssertionError(
            "Expected runtime_heartbeat_at_must_be_timezone_aware"
        )


def test_now_must_be_timezone_aware():
    aware_heartbeat = datetime.now(timezone.utc)

    try:
        is_runtime_heartbeat_stale(
            runtime_heartbeat_at=aware_heartbeat,
            now=datetime.utcnow(),
        )
    except ValueError as exc:
        assert str(exc) == "now_must_be_timezone_aware"
    else:
        raise AssertionError(
            "Expected now_must_be_timezone_aware"
        )


def test_stale_timeout_must_be_positive():
    now = datetime.now(timezone.utc)

    try:
        is_runtime_heartbeat_stale(
            runtime_heartbeat_at=now,
            now=now,
            stale_timeout_seconds=0,
        )
    except ValueError as exc:
        assert str(exc) == "stale_timeout_seconds_must_be_positive"
    else:
        raise AssertionError(
            "Expected stale_timeout_seconds_must_be_positive"
        )


def test_default_timeout_is_positive():
    assert DEFAULT_RUNTIME_STALE_TIMEOUT_SECONDS > 0
