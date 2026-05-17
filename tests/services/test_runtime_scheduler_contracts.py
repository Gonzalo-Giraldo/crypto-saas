from datetime import datetime, timezone

from apps.api.app.services.runtime_scheduler.contracts import (
    SchedulerTickContext,
)


def test_scheduler_tick_context_is_explicit_runtime_contract():
    ctx = SchedulerTickContext(
        scheduler_name="AUTO_PICK",
        started_monotonic=123.0,
        started_at_wall=datetime.now(timezone.utc),
        dry_run=True,
        trading_enabled=False,
        execution_mode="dry_run",
    )

    assert ctx.scheduler_name == "AUTO_PICK"
    assert ctx.execution_mode == "dry_run"
