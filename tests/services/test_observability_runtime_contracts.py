from apps.api.app.services.runtime_scheduler.observability_runtime import (
    record_scheduler_tick_error_runtime,
    record_scheduler_tick_success_runtime,
)
from apps.api.app.services.runtime_scheduler.runtime_state import (
    SchedulerRuntimeState,
)


def test_success_runtime_contract_exists():
    runtime_state = SchedulerRuntimeState(
        scheduler_dry_run=True,
        trading_enabled=False,
        execution_mode="dry_run",
    )

    try:
        record_scheduler_tick_success_runtime(
            db=object(),
            scheduler_name="AUTO_PICK",
            runtime_state=runtime_state,
            duration_ms=1,
        )
    except NotImplementedError:
        pass
    else:
        raise AssertionError("expected NotImplementedError")


def test_error_runtime_contract_exists():
    runtime_state = SchedulerRuntimeState(
        scheduler_dry_run=True,
        trading_enabled=False,
        execution_mode="dry_run",
    )

    try:
        record_scheduler_tick_error_runtime(
            db=object(),
            scheduler_name="AUTO_PICK",
            runtime_state=runtime_state,
            duration_ms=1,
            error="boom",
        )
    except NotImplementedError:
        pass
    else:
        raise AssertionError("expected NotImplementedError")
