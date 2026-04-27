from typing import Dict


RISK_LEVELS = {
    1: {
        "name": "conservative",
        "risk_pct": 0.5,
        "target_rr": 3.0,
        "min_rr": 2.0,
    },
    2: {
        "name": "balanced",
        "risk_pct": 1.0,
        "target_rr": 2.0,
        "min_rr": 1.5,
    },
    3: {
        "name": "aggressive",
        "risk_pct": 2.0,
        "target_rr": 1.5,
        "min_rr": 1.2,
    },
}


def resolve_risk_level(level: int) -> Dict:
    try:
        level_int = int(level)
    except Exception:
        raise ValueError("invalid risk level")

    config = RISK_LEVELS.get(level_int)
    if not config:
        raise ValueError("risk level must be 1, 2 or 3")

    return {
        "level": level_int,
        **config,
    }
