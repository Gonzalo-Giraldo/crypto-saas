from typing import Optional


def sort_exit_candidates(candidates: list[dict]) -> list[dict]:
    ordered = list(candidates)
    ordered.sort(key=lambda item: (item["priority"], -item["opened_minutes"]))
    return ordered


def resolve_policy_skip_reason_basic(
    *,
    dry_run: bool,
    paused: bool,
    errors: int,
    max_errors_per_tick: int,
    closed_positions: int,
    max_closes_per_tick: int,
    already_closed_symbol_in_tick: bool,
) -> Optional[str]:
    if errors >= max_errors_per_tick:
        return "max_errors_reached"
    if paused and not dry_run:
        return "paused"
    if (not dry_run) and max_closes_per_tick > 0 and closed_positions >= max_closes_per_tick:
        return "max_closes_reached"
    if (not dry_run) and already_closed_symbol_in_tick:
        return "symbol_cooldown_tick"
    return None
