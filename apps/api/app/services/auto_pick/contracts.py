from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Union


@dataclass(frozen=True)
class AutoPickDecision:
    """Selection-only decision. No sizing, risk, execution, order or fill data."""

    symbol: str
    side: Literal["BUY", "SELL"]
    direction: Literal["LONG", "SHORT"]
    broker: str
    asset_profile: Literal["CRYPTO", "EQUITY"]
    model_version: str
    final_score: float
    decision_reason: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AutoPickNoTrade:
    """Fail-closed Auto-Pick result when no safe selection is available."""

    broker: str
    reason: str
    model_version: str = "auto_pick_orchestrator_v1"
    evidence: dict[str, Any] = field(default_factory=dict)


AutoPickResult = Union[AutoPickDecision, AutoPickNoTrade]
