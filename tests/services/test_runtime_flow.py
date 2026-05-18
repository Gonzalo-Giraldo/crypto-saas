from unittest.mock import patch

from apps.api.app.services.runtime_scheduler.runtime_flow import (
    execute_scheduler_runtime_flow,
)


class ObservationReportStub:
    selected_symbol = None
    selected = None

    def to_dict(self):
        return {"ok": True}


@patch(
    "apps.api.app.services.runtime_scheduler.runtime_flow.run_binance_auto_pick_observation"
)
def test_runtime_flow_uses_injected_global_shadow_tick(mock_observation):
    mock_observation.return_value = ObservationReportStub()

    calls = []

    result, observation_report = execute_scheduler_runtime_flow(
        db=object(),
        started_at=0,
        scheduler_dry_run=True,
        legacy_exit_tick=lambda **_: {"scanned_positions": 0},
        legacy_market_monitor_tick=lambda **_: {"inserted": 0},
        legacy_auto_pick_tick=lambda **_: {"executed_count": 0},
        legacy_learning_tick=lambda **_: None,
        global_shadow_tick=lambda **kwargs: calls.append(kwargs) or None,
    )

    assert len(calls) == 1
    assert "db" in calls[0]
    assert observation_report is mock_observation.return_value
