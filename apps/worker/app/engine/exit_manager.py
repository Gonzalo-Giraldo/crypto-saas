
from apps.api.app.services.exit_policy_engine import compute_trailing_stop


def simulate_trailing_for_position(position: dict) -> dict | None:
    """
    Recibe una posición (dict) y devuelve qué haría el trailing.
    NO ejecuta nada.
    """

    try:
        symbol = position.get("symbol")
        side = position.get("side")
        entry = position.get("entry_price")
        stop_loss = position.get("stop_loss")
        current_price = position.get("current_price")
    except Exception:
        return None

    if not all([symbol, side, entry, stop_loss, current_price]):
        return None

    new_sl = compute_trailing_stop(
        side=side,
        entry_price=entry,
        stop_loss=stop_loss,
        current_price=current_price,
    )

    if new_sl is None:
        return None

    return {
        "symbol": symbol,
        "side": side,
        "entry_price": entry,
        "current_price": current_price,
        "old_sl": stop_loss,
        "new_sl": new_sl,
    }


def run_trailing_dry_run(positions: list[dict]) -> list[dict]:
    """
    Simula trailing sobre múltiples posiciones.
    """
    results = []

    for pos in positions:
        decision = simulate_trailing_for_position(pos)
        if decision:
            results.append(decision)

    return results
