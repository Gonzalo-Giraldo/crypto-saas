from fastapi import HTTPException, status


SIGNAL_TRANSITIONS: dict[str, set[str]] = {
    "CREATED": {"EXECUTING", "REJECTED", "CANCELLED"},
    "EXECUTING": {"OPENED", "REJECTED", "CANCELLED"},
    "OPENED": {"COMPLETED", "CANCELLED"},
    "REJECTED": set(),
    "CANCELLED": set(),
    "COMPLETED": set(),
}

POSITION_TRANSITIONS: dict[str, set[str]] = {
    "OPEN": {"CLOSED"},
    "CLOSED": set(),
}


def _norm(value: str) -> str:
    return (value or "").strip().upper()


def can_transition_signal(current: str, target: str) -> bool:
    cur = _norm(current)
    nxt = _norm(target)
    return nxt in SIGNAL_TRANSITIONS.get(cur, set())


def assert_signal_transition(current: str, target: str) -> None:
    cur = _norm(current)
    nxt = _norm(target)
    if nxt not in SIGNAL_TRANSITIONS.get(cur, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid signal transition: {cur} -> {nxt}",
        )


def assert_position_transition(current: str, target: str) -> None:
    cur = _norm(current)
    nxt = _norm(target)
    if nxt not in POSITION_TRANSITIONS.get(cur, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid position transition: {cur} -> {nxt}",
        )
