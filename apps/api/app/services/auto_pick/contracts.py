from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Union

from apps.api.app.services.risk.contracts import RiskSizingDecision


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


@dataclass(frozen=True)
class IntentCreateDraft:
    """Draft payload for intent creation. This does not execute anything."""

    broker: str
    symbol: str
    side: Literal["BUY", "SELL"]
    direction: Literal["LONG", "SHORT"]
    asset_profile: Literal["CRYPTO", "EQUITY"]
    model_version: str
    final_score: float
    decision_reason: str
    risk_sizing: RiskSizingDecision
    evidence: dict[str, Any] = field(default_factory=dict)
