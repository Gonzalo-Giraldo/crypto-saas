import time
from unittest.mock import Mock

from apps.api.app.services.runtime_scheduler.runtime_flow import execute_scheduler_runtime_flow
from apps.api.app.services.runtime_scheduler.runtime_dependencies import SchedulerRuntimeDependencies
from apps.api.app.services.auto_pick.contracts import AutoPickObservationReport


def test_runtime_flow_persists_autopick_observation_to_data_db(monkeypatch):
    report = AutoPickObservationReport(
        decision_status="NO_SELECTION",
        broker="BINANCE",
        reason="proof",
        no_selection_reason="proof",
        selected=None,
        selected_symbol=None,
        selected_rank=None,
        ranked_count=0,
        top_n=10,
        candidates=[],
    )

    persisted = {"called": False}

    monkeypatch.setattr(
        "apps.api.app.services.runtime_scheduler.runtime_flow.run_binance_auto_pick_observation",
        lambda top_n: report,
    )

    monkeypatch.setattr(
        "apps.api.app.services.runtime_scheduler.runtime_flow.persist_autopick_observation_report_to_data_db",
        lambda observation_report: persisted.update(called=True),
    )

    deps = SchedulerRuntimeDependencies(
        legacy_exit_tick=lambda **kwargs: {},
        legacy_market_monitor_tick=lambda **kwargs: {"inserted": 0},
        legacy_auto_pick_tick=lambda **kwargs: {"executed_count": 0},
        legacy_learning_tick=lambda **kwargs: None,
        global_shadow_tick=lambda **kwargs: None,
    )

    execute_scheduler_runtime_flow(
        db=Mock(),
        started_at=time.monotonic(),
        scheduler_dry_run=True,
        dependencies=deps,
    )

    assert persisted["called"] is True
