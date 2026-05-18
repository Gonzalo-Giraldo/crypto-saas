from apps.api.app.services.runtime_scheduler.runtime_state_builder import (
    build_scheduler_runtime_state,
)


def test_build_scheduler_runtime_state_dry_run_enabled():
    state = build_scheduler_runtime_state(
        scheduler_dry_run=True,
        trading_enabled=False,
    )

    assert state.scheduler_dry_run is True
    assert state.trading_enabled is False
    assert state.execution_mode == "dry_run"


def test_build_scheduler_runtime_state_live_enabled():
    state = build_scheduler_runtime_state(
        scheduler_dry_run=False,
        trading_enabled=True,
    )

    assert state.scheduler_dry_run is False
    assert state.trading_enabled is True
    assert state.execution_mode == "live"
