from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeTickOnceDependencies:
    db_factory: object
    settings: object
    build_tick_context: object
    elapsed_ms_since: object
    get_trading_enabled: object
    execute_runtime_adapter: object
    execute_runtime_error_adapter: object
    legacy_exit_tick: object
    legacy_market_monitor_tick: object
    legacy_auto_pick_tick: object
    legacy_learning_tick: object
    global_shadow_tick: object
    authority_observer: object | None = None
    print_fn: object = print


def run_runtime_tick_once(
    *,
    scheduler_name: str,
    deps: RuntimeTickOnceDependencies,
) -> None:
    tick_context = deps.build_tick_context(
        scheduler_name=scheduler_name,
    )
    started_at = tick_context.started_monotonic
    started_at_wall = tick_context.started_at_wall
    db = deps.db_factory()

    scheduler_dry_run = bool(deps.settings.AUTO_PICK_INTERNAL_SCHEDULER_DRY_RUN)

    try:
        def _execute_tick():
            return deps.execute_runtime_adapter(
                db=db,
                scheduler_name=scheduler_name,
                started_at=started_at,
                started_at_wall=started_at_wall,
                scheduler_dry_run=scheduler_dry_run,
                trading_enabled=deps.get_trading_enabled(db),
                legacy_exit_tick=deps.legacy_exit_tick,
                legacy_market_monitor_tick=deps.legacy_market_monitor_tick,
                legacy_auto_pick_tick=deps.legacy_auto_pick_tick,
                legacy_learning_tick=deps.legacy_learning_tick,
                global_shadow_tick=deps.global_shadow_tick,
            )

        if deps.authority_observer is None:
            flow_result = _execute_tick()
        else:
            observed = deps.authority_observer(fn=_execute_tick)
            flow_result = observed.result
        db.commit()

        deps.print_fn(
            "[auto-pick-scheduler] tick ok",
            flow_result.tick_details,
            flush=True,
        )
    except Exception as exc:
        try:
            duration_ms = deps.elapsed_ms_since(started_at)

            deps.execute_runtime_error_adapter(
                db=db,
                scheduler_name=scheduler_name,
                scheduler_dry_run=scheduler_dry_run,
                trading_enabled=deps.get_trading_enabled(db),
                duration_ms=duration_ms,
                started_at_wall=started_at_wall,
                error=str(exc),
            )
            db.commit()
        except Exception:
            db.rollback()

        deps.print_fn(
            f"[auto-pick-scheduler] tick error: {exc}",
            flush=True,
        )
    finally:
        db.close()
