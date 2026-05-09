from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Tuple


class ExecutionResolution(str, Enum):
    NOOP = "NOOP"
    KEEP_PROVISIONAL = "KEEP_PROVISIONAL"
    CREATE_AUTHORITATIVE = "CREATE_AUTHORITATIVE"
    REPLACE_AUTHORITATIVE = "REPLACE_AUTHORITATIVE"
    CLEANUP_PROVISIONAL = "CLEANUP_PROVISIONAL"
    ACTIVATE_TRAILING = "ACTIVATE_TRAILING"
    RECORD_AUDIT_ONLY = "RECORD_AUDIT_ONLY"


class ResolutionAuthority(str, Enum):
    AUDIT_AUTHORITY = "AUDIT_AUTHORITY"
    PROVISIONAL_AUTHORITY = "PROVISIONAL_AUTHORITY"
    AUTHORITATIVE_AUTHORITY = "AUTHORITATIVE_AUTHORITY"
    REPLACEMENT_AUTHORITY = "REPLACEMENT_AUTHORITY"
    CLEANUP_AUTHORITY = "CLEANUP_AUTHORITY"
    TRAILING_AUTHORITY = "TRAILING_AUTHORITY"


class ResolutionAuthorityReason(str, Enum):
    ALLOWED = "ALLOWED"
    CONVERGENCE_SEMANTICS_NOT_ALLOWED = "CONVERGENCE_SEMANTICS_NOT_ALLOWED"
    MISSING_REQUIRED_AUTHORITY = "MISSING_REQUIRED_AUTHORITY"
    FORBIDDEN_RESOLUTION = "FORBIDDEN_RESOLUTION"
    UNKNOWN_RESOLUTION_PRIORITY = "UNKNOWN_RESOLUTION_PRIORITY"
    COMPETING_RESOLUTION = "COMPETING_RESOLUTION"
    FINALITY_VIOLATION = "FINALITY_VIOLATION"
    LOCKED_RESOLUTION_VIOLATION = "LOCKED_RESOLUTION_VIOLATION"
    PROTECTION_CONTINUITY_REQUIRED = "PROTECTION_CONTINUITY_REQUIRED"


@dataclass(frozen=True)
class ResolutionPriority:
    resolution: ExecutionResolution
    priority: int


@dataclass(frozen=True)
class ExecutionResolutionAuthorityPolicy:
    required_authorities: FrozenSet[ResolutionAuthority]
    granted_authorities: FrozenSet[ResolutionAuthority]
    allowed_resolutions: FrozenSet[ExecutionResolution]
    forbidden_resolutions: FrozenSet[ExecutionResolution]
    priority_table: FrozenSet[ResolutionPriority]
    final_resolutions: FrozenSet[ExecutionResolution]
    locked_resolutions: FrozenSet[ExecutionResolution]
    requires_single_winner: bool = True
    requires_protection_continuity: bool = True


@dataclass(frozen=True)
class ExecutionResolutionAuthorityEvidence:
    candidate_resolutions: FrozenSet[ExecutionResolution]
    requested_resolution: ExecutionResolution
    protection_continuity_proven: bool


@dataclass(frozen=True)
class ExecutionResolutionAuthorityDecision:
    allowed: bool
    reason: ResolutionAuthorityReason
    selected_resolution: ExecutionResolution | None
    missing_authorities: Tuple[ResolutionAuthority, ...]
    forbidden_resolutions: Tuple[ExecutionResolution, ...]
    competing_resolutions: Tuple[ExecutionResolution, ...]
    finality_violations: Tuple[ExecutionResolution, ...]
    locked_resolution_violations: Tuple[ExecutionResolution, ...]


def _priority_lookup(
    priority_table: FrozenSet[ResolutionPriority],
) -> dict[ExecutionResolution, int]:
    return {entry.resolution: entry.priority for entry in priority_table}


def evaluate_execution_resolution_authority(
    *,
    convergence_semantics_allowed: bool,
    policy: ExecutionResolutionAuthorityPolicy,
    evidence: ExecutionResolutionAuthorityEvidence,
) -> ExecutionResolutionAuthorityDecision:
    """
    Pure deterministic execution resolution authority evaluator.

    This function does not execute, persist, retry, lock runtime resources,
    call broker APIs, call Binance APIs, inspect websocket state, inspect DB state,
    use time, IO, randomness, or async orchestration.

    It only selects or rejects a semantic resolution deterministically.
    """

    if not convergence_semantics_allowed:
        return ExecutionResolutionAuthorityDecision(
            allowed=False,
            reason=ResolutionAuthorityReason.CONVERGENCE_SEMANTICS_NOT_ALLOWED,
            selected_resolution=None,
            missing_authorities=(),
            forbidden_resolutions=(),
            competing_resolutions=(),
            finality_violations=(),
            locked_resolution_violations=(),
        )

    missing_authorities = tuple(
        sorted(
            policy.required_authorities - policy.granted_authorities,
            key=lambda item: item.value,
        )
    )
    if missing_authorities:
        return ExecutionResolutionAuthorityDecision(
            allowed=False,
            reason=ResolutionAuthorityReason.MISSING_REQUIRED_AUTHORITY,
            selected_resolution=None,
            missing_authorities=missing_authorities,
            forbidden_resolutions=(),
            competing_resolutions=(),
            finality_violations=(),
            locked_resolution_violations=(),
        )

    forbidden_resolutions = tuple(
        sorted(
            evidence.candidate_resolutions & policy.forbidden_resolutions,
            key=lambda item: item.value,
        )
    )
    if forbidden_resolutions:
        return ExecutionResolutionAuthorityDecision(
            allowed=False,
            reason=ResolutionAuthorityReason.FORBIDDEN_RESOLUTION,
            selected_resolution=None,
            missing_authorities=(),
            forbidden_resolutions=forbidden_resolutions,
            competing_resolutions=(),
            finality_violations=(),
            locked_resolution_violations=(),
        )

    disallowed_resolutions = tuple(
        sorted(
            evidence.candidate_resolutions - policy.allowed_resolutions,
            key=lambda item: item.value,
        )
    )
    if disallowed_resolutions:
        return ExecutionResolutionAuthorityDecision(
            allowed=False,
            reason=ResolutionAuthorityReason.FORBIDDEN_RESOLUTION,
            selected_resolution=None,
            missing_authorities=(),
            forbidden_resolutions=disallowed_resolutions,
            competing_resolutions=(),
            finality_violations=(),
            locked_resolution_violations=(),
        )

    priorities = _priority_lookup(policy.priority_table)

    unknown_priority_resolutions = tuple(
        sorted(
            (
                resolution
                for resolution in evidence.candidate_resolutions
                if resolution not in priorities
            ),
            key=lambda item: item.value,
        )
    )
    if unknown_priority_resolutions:
        return ExecutionResolutionAuthorityDecision(
            allowed=False,
            reason=ResolutionAuthorityReason.UNKNOWN_RESOLUTION_PRIORITY,
            selected_resolution=None,
            missing_authorities=(),
            forbidden_resolutions=(),
            competing_resolutions=unknown_priority_resolutions,
            finality_violations=(),
            locked_resolution_violations=(),
        )

    selected_resolution = min(
        evidence.candidate_resolutions,
        key=lambda resolution: (priorities[resolution], resolution.value),
    )

    same_priority_competitors = tuple(
        sorted(
            (
                resolution
                for resolution in evidence.candidate_resolutions
                if resolution != selected_resolution
                and priorities[resolution] == priorities[selected_resolution]
            ),
            key=lambda item: item.value,
        )
    )
    if policy.requires_single_winner and same_priority_competitors:
        return ExecutionResolutionAuthorityDecision(
            allowed=False,
            reason=ResolutionAuthorityReason.COMPETING_RESOLUTION,
            selected_resolution=None,
            missing_authorities=(),
            forbidden_resolutions=(),
            competing_resolutions=tuple(
                sorted(
                    {selected_resolution, *same_priority_competitors},
                    key=lambda item: item.value,
                )
            ),
            finality_violations=(),
            locked_resolution_violations=(),
        )

    if evidence.requested_resolution != selected_resolution:
        return ExecutionResolutionAuthorityDecision(
            allowed=False,
            reason=ResolutionAuthorityReason.COMPETING_RESOLUTION,
            selected_resolution=selected_resolution,
            missing_authorities=(),
            forbidden_resolutions=(),
            competing_resolutions=(evidence.requested_resolution,),
            finality_violations=(),
            locked_resolution_violations=(),
        )

    finality_violations = tuple(
        sorted(
            policy.final_resolutions
            & evidence.candidate_resolutions
            - frozenset({selected_resolution}),
            key=lambda item: item.value,
        )
    )
    if finality_violations:
        return ExecutionResolutionAuthorityDecision(
            allowed=False,
            reason=ResolutionAuthorityReason.FINALITY_VIOLATION,
            selected_resolution=selected_resolution,
            missing_authorities=(),
            forbidden_resolutions=(),
            competing_resolutions=(),
            finality_violations=finality_violations,
            locked_resolution_violations=(),
        )

    locked_resolution_violations = tuple(
        sorted(
            policy.locked_resolutions
            & evidence.candidate_resolutions
            - frozenset({selected_resolution}),
            key=lambda item: item.value,
        )
    )
    if locked_resolution_violations:
        return ExecutionResolutionAuthorityDecision(
            allowed=False,
            reason=ResolutionAuthorityReason.LOCKED_RESOLUTION_VIOLATION,
            selected_resolution=selected_resolution,
            missing_authorities=(),
            forbidden_resolutions=(),
            competing_resolutions=(),
            finality_violations=(),
            locked_resolution_violations=locked_resolution_violations,
        )

    if (
        policy.requires_protection_continuity
        and not evidence.protection_continuity_proven
    ):
        return ExecutionResolutionAuthorityDecision(
            allowed=False,
            reason=ResolutionAuthorityReason.PROTECTION_CONTINUITY_REQUIRED,
            selected_resolution=selected_resolution,
            missing_authorities=(),
            forbidden_resolutions=(),
            competing_resolutions=(),
            finality_violations=(),
            locked_resolution_violations=(),
        )

    return ExecutionResolutionAuthorityDecision(
        allowed=True,
        reason=ResolutionAuthorityReason.ALLOWED,
        selected_resolution=selected_resolution,
        missing_authorities=(),
        forbidden_resolutions=(),
        competing_resolutions=(),
        finality_violations=(),
        locked_resolution_violations=(),
    )
