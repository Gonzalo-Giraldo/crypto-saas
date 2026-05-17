from __future__ import annotations


def execute_autopick_tick_flow(fn):
    return fn()


def execute_with_runner(
    *,
    runner,
    fn,
):
    return runner.run_with_db_transaction(
        lambda: execute_autopick_tick_flow(fn)
    )

from apps.api.app.services.runtime_scheduler.autopick_tick_dependencies import (
    AutopickTickDependencies,
)


def run_autopick_tick(
    deps: AutopickTickDependencies,
    fn,
):
    return fn(deps)
