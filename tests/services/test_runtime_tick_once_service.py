from dataclasses import dataclass

from apps.api.app.services.runtime_scheduler.runtime_tick_once_service import (
    RuntimeTickOnceDependencies,
    run_runtime_tick_once,
)


@dataclass(frozen=True)
class _TickContext:
    started_monotonic: float = 10.0
    started_at_wall: object = "wall-time"


class _Settings:
    AUTO_PICK_INTERNAL_SCHEDULER_DRY_RUN = True


class _FlowResult:
    tick_details = {"ok": True}


class _DB:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _base_deps(*, db, adapter, error_adapter=None, prints=None):
    if prints is None:
        prints = []

    return RuntimeTickOnceDependencies(
        db_factory=lambda: db,
        settings=_Settings(),
        build_tick_context=lambda *, scheduler_name: _TickContext(),
        elapsed_ms_since=lambda started_at: 123,
        get_trading_enabled=lambda db: False,
        execute_runtime_adapter=adapter,
        execute_runtime_error_adapter=error_adapter or (lambda **kwargs: None),
        legacy_exit_tick=lambda **kwargs: None,
        legacy_market_monitor_tick=lambda **kwargs: None,
        legacy_auto_pick_tick=lambda **kwargs: None,
        legacy_learning_tick=lambda **kwargs: None,
        global_shadow_tick=lambda **kwargs: None,
        print_fn=lambda *args, **kwargs: prints.append((args, kwargs)),
    )


def test_run_runtime_tick_once_commits_success_and_closes_db():
    db = _DB()
    calls = []

    def adapter(**kwargs):
        calls.append(kwargs)
        return _FlowResult()

    run_runtime_tick_once(
        scheduler_name="auto_pick_internal",
        deps=_base_deps(db=db, adapter=adapter),
    )

    assert db.committed is True
    assert db.rolled_back is False
    assert db.closed is True
    assert calls[0]["scheduler_name"] == "auto_pick_internal"
    assert calls[0]["scheduler_dry_run"] is True
    assert calls[0]["trading_enabled"] is False


def test_run_runtime_tick_once_records_error_and_commits_error_adapter():
    db = _DB()
    calls = []

    def adapter(**kwargs):
        raise RuntimeError("boom")

    def error_adapter(**kwargs):
        calls.append(kwargs)

    run_runtime_tick_once(
        scheduler_name="auto_pick_internal",
        deps=_base_deps(db=db, adapter=adapter, error_adapter=error_adapter),
    )

    assert db.committed is True
    assert db.rolled_back is False
    assert db.closed is True
    assert calls[0]["scheduler_name"] == "auto_pick_internal"
    assert calls[0]["duration_ms"] == 123
    assert calls[0]["error"] == "boom"


def test_run_runtime_tick_once_rolls_back_if_error_adapter_fails():
    db = _DB()

    def adapter(**kwargs):
        raise RuntimeError("boom")

    def error_adapter(**kwargs):
        raise RuntimeError("error_adapter_failed")

    run_runtime_tick_once(
        scheduler_name="auto_pick_internal",
        deps=_base_deps(db=db, adapter=adapter, error_adapter=error_adapter),
    )

    assert db.committed is False
    assert db.rolled_back is True
    assert db.closed is True

def test_runtime_tick_once_optional_authority_observer_wraps_tick_without_blocking():
    calls = []

    class Observed:
        def __init__(self, result):
            self.result = result

    def authority_observer(*, fn):
        calls.append("observer")
        return Observed(fn())

    db = _DB()

    def adapter(**_kwargs):
        return _FlowResult()

    deps = _base_deps(
        db=db,
        adapter=adapter,
    )
    deps = RuntimeTickOnceDependencies(
        **{
            **deps.__dict__,
            "authority_observer": authority_observer,
        }
    )

    run_runtime_tick_once(
        scheduler_name="auto_pick_internal",
        deps=deps,
    )

    assert calls == ["observer"]
    assert db.committed is True


def test_runtime_tick_once_observer_does_not_swallow_tick_exception():
    calls = []

    class ExplodingAdapter:
        def __call__(self, **_kwargs):
            calls.append("tick")
            raise RuntimeError("tick exploded")

    class Observed:
        def __init__(self, result):
            self.result = result

    def authority_observer(*, fn):
        calls.append("observer")
        return Observed(fn())

    db = _DB()

    deps = _base_deps(
        db=db,
        adapter=ExplodingAdapter(),
    )
    deps = RuntimeTickOnceDependencies(
        **{
            **deps.__dict__,
            "authority_observer": authority_observer,
        }
    )

    run_runtime_tick_once(
        scheduler_name="auto_pick_internal",
        deps=deps,
    )

    assert calls == ["observer", "tick"]
    assert db.rolled_back is False
    assert db.committed is True
