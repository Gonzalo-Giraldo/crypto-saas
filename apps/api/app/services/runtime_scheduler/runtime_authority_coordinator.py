from __future__ import annotations

from dataclasses import dataclass

from apps.api.app.services.runtime_scheduler.runtime_advisory_session import (
    RuntimeAdvisorySessionState,
)
from apps.api.app.services.runtime_scheduler.runtime_session_authority import (
    RuntimeSessionAuthorityDecision,
    RuntimeSessionAuthorityEvidence,
    evaluate_runtime_session_authority,
)


@dataclass(frozen=True)
class RuntimeAuthorityCoordinatorInput:
    ownership_row_present: bool
    local_identity_matches: bool
    generation_matches: bool
    heartbeat_fresh: bool
    runtime_health_valid: bool
    advisory_session_state: RuntimeAdvisorySessionState


@dataclass(frozen=True)
class RuntimeAuthorityCoordinatorResult:
    valid: bool
    reason: str | None
    evidence: RuntimeSessionAuthorityEvidence
    advisory_session_reason: str | None


def evaluate_runtime_authority(
    *,
    authority_input: RuntimeAuthorityCoordinatorInput,
) -> RuntimeAuthorityCoordinatorResult:
    evidence = RuntimeSessionAuthorityEvidence(
        ownership_row_present=authority_input.ownership_row_present,
        advisory_session_valid=authority_input.advisory_session_state.valid,
        local_identity_matches=authority_input.local_identity_matches,
        generation_matches=authority_input.generation_matches,
        heartbeat_fresh=authority_input.heartbeat_fresh,
        runtime_health_valid=authority_input.runtime_health_valid,
    )

    decision: RuntimeSessionAuthorityDecision = evaluate_runtime_session_authority(
        evidence=evidence,
    )

    return RuntimeAuthorityCoordinatorResult(
        valid=decision.valid,
        reason=decision.reason,
        evidence=evidence,
        advisory_session_reason=authority_input.advisory_session_state.reason,
    )
