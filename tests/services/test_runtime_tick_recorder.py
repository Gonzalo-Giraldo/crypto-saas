from apps.api.app.services.runtime_scheduler.runtime_tick_recorder import (
    record_tick_failure,
    record_tick_success,
)


def test_runtime_tick_recorder_exports_explicit_runtime_api():
    assert callable(record_tick_success)
    assert callable(record_tick_failure)
