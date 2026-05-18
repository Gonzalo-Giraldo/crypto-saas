from unittest.mock import patch

from apps.api.app.services.runtime_scheduler.observability_runtime import (
    record_scheduler_tick_error_runtime,
    record_scheduler_tick_success_runtime,
)
from apps.api.app.services.runtime_scheduler.runtime_state import (
    SchedulerRuntimeState,
)


class ObservationReportStub:
    decision_status = "OK"
    selected_rank = 1
    ranked_count = 1
    top_n = 1


@patch(
    "apps.api.app.services.runtime_scheduler.observability_runtime.record_scheduler_tick_journal"
)
@patch(
    "apps.api.app.services.runtime_scheduler.observability_runtime.record_scheduler_tick_ok"
)
def test_success_runtime_contract_exists(
    _mock_ok,
    _mock_journal,
):
    runtime_state = SchedulerRuntimeState(
        scheduler_dry_run=True,
        trading_enabled=False,
        execution_mode="dry_run",
    )

    record_scheduler_tick_success_runtime(
        db=object(),
        scheduler_name="AUTO_PICK",
        runtime_state=runtime_state,
        duration_ms=1,
        started_at=None,
        candidate_symbol=None,
        candidate_score=None,
        observation_report=ObservationReportStub(),
        observation_payload={},
    )


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
