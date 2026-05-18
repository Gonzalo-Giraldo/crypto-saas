from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SchedulerRuntimeFlowResult:
    duration_ms: int
    tick_details: dict
    observation_payload: dict
    candidate_symbol: str | None
    candidate_score: str | None
