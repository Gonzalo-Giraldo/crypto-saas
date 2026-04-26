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



def compute_trailing_stop(
    *,
    side: str,
    entry_price: float,
    stop_loss: float,
    current_price: float,
) -> float | None:
    try:
        side_norm = str(side or "").upper().strip()
        entry = float(entry_price)
        current_sl = float(stop_loss)
        price = float(current_price)
    except Exception:
        return None

    if side_norm not in {"BUY", "SELL"}:
        return None
    if entry <= 0 or current_sl <= 0 or price <= 0:
        return None

    risk_abs = abs(entry - current_sl)
    if risk_abs <= 0:
        return None

    if side_norm == "BUY":
        profit = price - entry
        if profit >= 3 * risk_abs:
            candidate_sl = entry + 2 * risk_abs
        elif profit >= 2 * risk_abs:
            candidate_sl = entry + risk_abs
        elif profit >= risk_abs:
            candidate_sl = entry
        else:
            return None

        if candidate_sl > current_sl:
            return candidate_sl
        return None

    profit = entry - price
    if profit >= 3 * risk_abs:
        candidate_sl = entry - 2 * risk_abs
    elif profit >= 2 * risk_abs:
        candidate_sl = entry - risk_abs
    elif profit >= risk_abs:
        candidate_sl = entry
    else:
        return None

    if candidate_sl < current_sl:
        return candidate_sl
    return None
