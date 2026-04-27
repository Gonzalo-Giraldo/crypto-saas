from typing import Dict


STRATEGY_CAPITAL_ALLOCATIONS = {
    "SWING_V1": 0.40,
    "INTRADAY": 0.35,
}


def resolve_strategy_capital(
    *,
    strategy_id: str,
    broker_balance_usdt: float,
) -> Dict:
    strategy = str(strategy_id or "").strip().upper()

    if not strategy:
        raise ValueError("strategy_id is required")

    if broker_balance_usdt <= 0:
        raise ValueError("broker_balance_usdt must be positive")

    allocation_pct = STRATEGY_CAPITAL_ALLOCATIONS.get(strategy)

    if allocation_pct is None:
        raise ValueError(f"unknown strategy_id: {strategy}")

    capital_base = float(broker_balance_usdt) * float(allocation_pct)

    return {
        "strategy_id": strategy,
        "broker_balance_usdt": float(broker_balance_usdt),
        "allocation_pct": float(allocation_pct),
        "capital_base": float(capital_base),
    }
