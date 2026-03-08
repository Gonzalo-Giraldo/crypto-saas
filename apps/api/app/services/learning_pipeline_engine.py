from fastapi import HTTPException, status


def validate_range_param(*, name: str, value: int, minimum: int, maximum: int) -> int:
    out = int(value)
    if out < minimum or out > maximum:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{name} must be between {minimum} and {maximum}",
        )
    return out


def validate_choice_param(*, name: str, value: str, allowed: set[str]) -> str:
    normalized = str(value or "").upper().strip()
    if normalized not in allowed:
        allowed_txt = ", ".join(sorted(allowed))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{name} must be one of: {allowed_txt}",
        )
    return normalized


def compute_rate(numerator: int, denominator: int) -> float:
    num = max(0, int(numerator))
    den = max(0, int(denominator))
    if den == 0:
        return 0.0
    return round((num / den) * 100.0, 2)
