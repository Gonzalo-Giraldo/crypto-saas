from dataclasses import dataclass


@dataclass(frozen=True)
class ProtectionDecision:
    allowed: bool
    reason: str
    current_state: str
    next_state: str | None
