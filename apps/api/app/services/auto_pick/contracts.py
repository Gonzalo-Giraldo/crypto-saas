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



@dataclass(frozen=True)
class AutoPickCandidateProjection:
    """Read-only projected Auto-Pick candidate for observability/analytics."""

    rank: int
    symbol: str | None
    side: str | None
    valid: bool
    reason: str | None
    final_score: float | None
    selected: bool
    entry_price_reference: float | None
    features: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "symbol": self.symbol,
            "side": self.side,
            "valid": self.valid,
            "reason": self.reason,
            "final_score": self.final_score,
            "selected": self.selected,
            "entry_price_reference": self.entry_price_reference,
            "features": dict(self.features),
        }


@dataclass(frozen=True)
class AutoPickObservationReport:
    """
    Read-only autonomous Auto-Pick report.

    This contract is observational only:
    - no Risk
    - no Intent
    - no DB authority
    - no broker mutation
    """

    decision_status: str
    broker: str
    reason: str
    no_selection_reason: str | None
    selected: AutoPickCandidateProjection | None
    selected_symbol: str | None
    selected_rank: int | None
    ranked_count: int
    top_n: int
    candidates: list[AutoPickCandidateProjection] = field(default_factory=list)
    rejected_candidates: list[dict[str, Any]] = field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None
    production_priority: bool = True
    model_version: str = "binance_auto_pick_pipeline_v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_status": self.decision_status,
            "broker": self.broker,
            "reason": self.reason,
            "no_selection_reason": self.no_selection_reason,
            "selected": self.selected.to_dict() if self.selected else None,
            "selected_symbol": self.selected_symbol,
            "selected_rank": self.selected_rank,
            "ranked_count": self.ranked_count,
            "top_n": self.top_n,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "rejected_candidates": [dict(candidate) for candidate in self.rejected_candidates],
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "production_priority": self.production_priority,
            "model_version": self.model_version,
        }
