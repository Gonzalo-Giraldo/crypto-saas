from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeSessionAuthorityEvidence:
    ownership_row_present: bool
    advisory_session_valid: bool
    local_identity_matches: bool
    generation_matches: bool
    heartbeat_fresh: bool
    runtime_health_valid: bool


@dataclass(frozen=True)
class RuntimeSessionAuthorityDecision:
    valid: bool
    reason: str | None


def evaluate_runtime_session_authority(
    *,
    evidence: RuntimeSessionAuthorityEvidence,
) -> RuntimeSessionAuthorityDecision:
    if not evidence.ownership_row_present:
        return RuntimeSessionAuthorityDecision(
            valid=False,
            reason="ownership_row_not_present",
        )

    if not evidence.advisory_session_valid:
        return RuntimeSessionAuthorityDecision(
            valid=False,
            reason="advisory_session_not_valid",
        )

    if not evidence.local_identity_matches:
        return RuntimeSessionAuthorityDecision(
            valid=False,
            reason="local_identity_mismatch",
        )

    if not evidence.generation_matches:
        return RuntimeSessionAuthorityDecision(
            valid=False,
            reason="runtime_generation_mismatch",
        )

    if not evidence.heartbeat_fresh:
        return RuntimeSessionAuthorityDecision(
            valid=False,
            reason="runtime_heartbeat_stale",
        )

    if not evidence.runtime_health_valid:
        return RuntimeSessionAuthorityDecision(
            valid=False,
            reason="runtime_health_invalid",
        )

    return RuntimeSessionAuthorityDecision(
        valid=True,
        reason=None,
    )
