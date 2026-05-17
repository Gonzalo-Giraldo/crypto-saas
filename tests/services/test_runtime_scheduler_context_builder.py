from apps.api.app.services.runtime_scheduler.context_builder import (
    build_scheduler_tick_context,
)


def test_context_builder_creates_explicit_runtime_tick_context():
    ctx = build_scheduler_tick_context(
        scheduler_name="AUTO_PICK",
        dry_run=True,
        trading_enabled=False,
        execution_mode="dry_run",
    )

    assert ctx.scheduler_name == "AUTO_PICK"
    assert ctx.dry_run is True
    assert ctx.execution_mode == "dry_run"
