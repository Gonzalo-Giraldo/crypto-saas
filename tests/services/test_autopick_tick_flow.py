from apps.api.app.services.runtime_scheduler.autopick_tick_flow import (
    execute_autopick_tick_flow,
    execute_with_runner,
    run_autopick_tick,
)
from apps.api.app.services.runtime_scheduler.autopick_tick_dependencies import (
    AutopickTickDependencies,
)


def test_execute_autopick_tick_flow_returns_result():
    out = execute_autopick_tick_flow(
        lambda: {"status": "ok"}
    )

    assert out == {"status": "ok"}


def test_execute_with_runner_uses_runtime_runner():
    calls = []

    class Runner:
        def run_with_db_transaction(self, fn):
            calls.append("runner_called")
            return fn()

    out = execute_with_runner(
        runner=Runner(),
        fn=lambda: {"ok": True},
    )

    assert out == {"ok": True}
    assert calls == ["runner_called"]


def test_run_autopick_tick_uses_dependency_contract():
    class Settings:
        pass

    deps = AutopickTickDependencies(
        db=object(),
        settings=Settings(),
    )

    out = run_autopick_tick(
        deps,
        lambda ctx: {"has_settings": ctx.settings is not None},
    )

    assert out["has_settings"] is True


def test_execute_with_runner_can_use_optional_observer_without_transaction_wrapper():
    calls = []

    class Runner:
        def run_with_db_transaction(self, fn):
            calls.append("transaction_runner_called")
            return fn()

        def run(self, fn, *, observer=None):
            calls.append("runner_called")
            return observer(fn)

    def observer(fn):
        calls.append("observer_called")
        return fn()

    out = execute_with_runner(
        runner=Runner(),
        fn=lambda: {"ok": True},
        observer=observer,
    )

    assert out == {"ok": True}
    assert calls == ["runner_called", "observer_called"]


def test_execute_with_runner_preserves_transaction_path_without_observer():
    calls = []

    class Runner:
        def run_with_db_transaction(self, fn):
            calls.append("transaction_runner_called")
            return fn()

        def run(self, fn, *, observer=None):
            raise AssertionError("run should not be used without observer")

    out = execute_with_runner(
        runner=Runner(),
        fn=lambda: {"ok": True},
    )

    assert out == {"ok": True}
    assert calls == ["transaction_runner_called"]
