from unittest.mock import patch

from apps.api.app.services.runtime_scheduler.runtime_dependencies import (
    SchedulerRuntimeDependencies,
)
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

    dependencies = SchedulerRuntimeDependencies(
        legacy_exit_tick=lambda **_: {"scanned_positions": 0},
        legacy_market_monitor_tick=lambda **_: {"inserted": 0},
        legacy_auto_pick_tick=lambda **_: {"executed_count": 0},
        legacy_learning_tick=lambda **_: None,
        global_shadow_tick=lambda **kwargs: calls.append(kwargs) or None,
    )

    result, observation_report = execute_scheduler_runtime_flow(
        db=object(),
        started_at=0,
        scheduler_dry_run=True,
        dependencies=dependencies,
    )

    assert len(calls) == 1
    assert "db" in calls[0]
    assert observation_report is mock_observation.return_value


def test_runtime_flow_projects_shadow_output_into_observation_payload(mock_observation=None):
    class Report:
        selected_symbol = "BTCUSDT"
        selected_rank = 1
        ranked_count = 1
        top_n = 10
        decision_status = "SELECTED"

        class Selected:
            final_score = 0.91

        selected = Selected()

        def to_dict(self):
            return {
                "decision_status": "SELECTED",
                "selected_symbol": "BTCUSDT",
            }

    with patch(
        "apps.api.app.services.runtime_scheduler.runtime_flow.run_binance_auto_pick_observation",
        return_value=Report(),
    ):
        result, _ = execute_scheduler_runtime_flow(
            db=object(),
            started_at=0,
            scheduler_dry_run=True,
            dependencies=SchedulerRuntimeDependencies(
                legacy_exit_tick=lambda **_: {"scanned_positions": 0},
                legacy_market_monitor_tick=lambda **_: {"inserted": 0},
                legacy_auto_pick_tick=lambda **_: {"executed_count": 0},
                legacy_learning_tick=lambda **_: None,
                global_shadow_tick=lambda **_: {
                    "status": "shadow_ok",
                    "snapshot_id": "snapshot-1",
                    "diverged": False,
                },
            ),
        )

    assert result.observation_payload["shadow"]["status"] == "shadow_ok"
    assert result.observation_payload["shadow"]["diverged"] is False


def test_runtime_flow_projects_shadow_comparison_when_shadow_report_exists():
    class Report:
        selected_symbol = "BTCUSDT"
        selected_rank = 1
        ranked_count = 3
        top_n = 10
        decision_status = "SELECTED"

        class Selected:
            final_score = 0.91

        selected = Selected()

        def to_dict(self):
            return {
                "decision_status": "SELECTED",
                "selected_symbol": "BTCUSDT",
                "selected_rank": 1,
                "ranked_count": 3,
            }

    shadow_report = Report()
    shadow_report.selected_symbol = "ETHUSDT"
    shadow_report.ranked_count = 4

    with patch(
        "apps.api.app.services.runtime_scheduler.runtime_flow.run_binance_auto_pick_observation",
        return_value=Report(),
    ):
        result, _ = execute_scheduler_runtime_flow(
            db=object(),
            started_at=0,
            scheduler_dry_run=True,
            dependencies=SchedulerRuntimeDependencies(
                legacy_exit_tick=lambda **_: {"scanned_positions": 0},
                legacy_market_monitor_tick=lambda **_: {"inserted": 0},
                legacy_auto_pick_tick=lambda **_: {"executed_count": 0},
                legacy_learning_tick=lambda **_: None,
                global_shadow_tick=lambda **_: {
                    "status": "shadow_ok",
                    "report": shadow_report,
                },
            ),
        )

    comparison = result.observation_payload["shadow"]["comparison"]

    assert comparison["diverged"] is True
    assert comparison["fields"]["selected_symbol"] == {
        "legacy": "BTCUSDT",
        "shadow": "ETHUSDT",
    }
    assert comparison["fields"]["ranked_count"] == {
        "legacy": 3,
        "shadow": 4,
    }
