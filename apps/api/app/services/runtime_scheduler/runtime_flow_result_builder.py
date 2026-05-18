from __future__ import annotations

from apps.api.app.services.runtime_scheduler.runtime_flow_result import (
    SchedulerRuntimeFlowResult,
)


def build_scheduler_runtime_flow_result(
    *,
    duration_ms: int,
    tick_details: dict,
    observation_payload: dict,
    candidate_symbol: str | None,
    candidate_score: str | None,
) -> SchedulerRuntimeFlowResult:
    return SchedulerRuntimeFlowResult(
        duration_ms=duration_ms,
        tick_details=tick_details,
        observation_payload=observation_payload,
        candidate_symbol=candidate_symbol,
        candidate_score=candidate_score,
    )
