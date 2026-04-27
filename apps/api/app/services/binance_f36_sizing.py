from apps.api.app.services.position_sizing import compute_position_size
from apps.api.app.services.risk_level_resolver import resolve_risk_level
from apps.api.app.services.strategy_capital import resolve_strategy_capital


def compute_binance_f36_sizing(
    *,
    entry_price: float,
    stop_loss: float,
    usdt_free: float,
    strategy_id: str,
    risk_level: int,
) -> dict:
    try:
        sc = resolve_strategy_capital(
            strategy_id=strategy_id,
            broker_balance_usdt=float(usdt_free),
        )
        rl = resolve_risk_level(risk_level)

        sizing = compute_position_size(
            entry_price=float(entry_price),
            stop_loss=float(stop_loss),
            capital_base=float(sc["capital_base"]),
            risk_pct=float(rl["risk_pct"]),
        )
    except Exception as exc:
        raise ValueError(f"binance_f36_sizing_failed: {exc}") from exc

    return {
        "qty_final": sizing["qty_final"],
        "qty_raw": sizing["qty_raw"],
        "qty_cap": sizing["qty_cap"],
        "risk_real": sizing["risk_real"],
        "capital_base": sc["capital_base"],
    }
