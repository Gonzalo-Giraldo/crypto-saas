from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Tuple


class FinalityResolution(str, Enum):
    NOOP = "NOOP"
    KEEP_PROVISIONAL = "KEEP_PROVISIONAL"
    CREATE_AUTHORITATIVE = "CREATE_AUTHORITATIVE"
    REPLACE_AUTHORITATIVE = "REPLACE_AUTHORITATIVE"
    CLEANUP_PROVISIONAL = "CLEANUP_PROVISIONAL"
    ACTIVATE_TRAILING = "ACTIVATE_TRAILING"
    RECORD_AUDIT_ONLY = "RECORD_AUDIT_ONLY"


class FinalityEvidenceRequirement(str, Enum):
    AUTHORITATIVE_VERIFIED = "AUTHORITATIVE_VERIFIED"
    REPLACEMENT_RECONCILED = "REPLACEMENT_RECONCILED"
    CLEANUP_CONFIRMED = "CLEANUP_CONFIRMED"
    STABLE_BASELINE_CONFIRMED = "STABLE_BASELINE_CONFIRMED"
    TRAILING_CONFIRMED = "TRAILING_CONFIRMED"
    AUDIT_TRACE_COMPLETE = "AUDIT_TRACE_COMPLETE"


class FinalityReason(str, Enum):
    ALLOWED = "ALLOWED"
    RESOLUTION_AUTHORITY_NOT_ALLOWED = "RESOLUTION_AUTHORITY_NOT_ALLOWED"
    MISSING_FINALITY_EVIDENCE = "MISSING_FINALITY_EVIDENCE"
    FORBIDDEN_FINALIZATION = "FORBIDDEN_FINALIZATION"
    ALREADY_FINALIZED = "ALREADY_FINALIZED"
    POST_FINALIZATION_MUTATION = "POST_FINALIZATION_MUTATION"
    FINALITY_LOCK_VIOLATION = "FINALITY_LOCK_VIOLATION"
    PROTECTION_CONTINUITY_REQUIRED = "PROTECTION_CONTINUITY_REQUIRED"


@dataclass(frozen=True)
class ResolutionFinalityPolicy:
    finalizable_resolutions: FrozenSet[FinalityResolution]
    forbidden_finalizations: FrozenSet[FinalityResolution]
    already_finalized_resolutions: FrozenSet[FinalityResolution]
    locked_finality_resolutions: FrozenSet[FinalityResolution]
    required_finality_evidence: FrozenSet[FinalityEvidenceRequirement]
    mutation_resolutions: FrozenSet[FinalityResolution]
    requires_protection_continuity: bool = True


@dataclass(frozen=True)
class ResolutionFinalityEvidence:
    requested_finalization: FinalityResolution
    provided_finality_evidence: FrozenSet[FinalityEvidenceRequirement]
    protection_continuity_proven: bool


@dataclass(frozen=True)
class ResolutionFinalityDecision:
    allowed: bool
    reason: FinalityReason
    finalized_resolution: FinalityResolution | None
    missing_finality_evidence: Tuple[FinalityEvidenceRequirement, ...]
    forbidden_finalizations: Tuple[FinalityResolution, ...]
    already_finalized_resolutions: Tuple[FinalityResolution, ...]
    locked_finality_violations: Tuple[FinalityResolution, ...]


def evaluate_resolution_finality_semantics(
    *,
    resolution_authority_allowed: bool,
    policy: ResolutionFinalityPolicy,
    evidence: ResolutionFinalityEvidence,
) -> ResolutionFinalityDecision:
    """
    Pure deterministic resolution finality evaluator.

    This function does not execute, persist, lock runtime resources,
    call broker APIs, call Binance APIs, inspect websocket state, inspect DB state,
    use time, IO, randomness, or async orchestration.

    It only decides whether a semantic resolution may become final.
    """

    if not resolution_authority_allowed:
        return ResolutionFinalityDecision(
            allowed=False,
            reason=FinalityReason.RESOLUTION_AUTHORITY_NOT_ALLOWED,
            finalized_resolution=None,
            missing_finality_evidence=(),
            forbidden_finalizations=(),
            already_finalized_resolutions=(),
            locked_finality_violations=(),
        )

    if evidence.requested_finalization in policy.forbidden_finalizations:
        return ResolutionFinalityDecision(
            allowed=False,
            reason=FinalityReason.FORBIDDEN_FINALIZATION,
            finalized_resolution=None,
            missing_finality_evidence=(),
            forbidden_finalizations=(evidence.requested_finalization,),
            already_finalized_resolutions=(),
            locked_finality_violations=(),
        )

    if evidence.requested_finalization not in policy.finalizable_resolutions:
        return ResolutionFinalityDecision(
            allowed=False,
            reason=FinalityReason.FORBIDDEN_FINALIZATION,
            finalized_resolution=None,
            missing_finality_evidence=(),
            forbidden_finalizations=(evidence.requested_finalization,),
            already_finalized_resolutions=(),
            locked_finality_violations=(),
        )

    already_finalized = tuple(
        sorted(
            policy.already_finalized_resolutions
            & frozenset({evidence.requested_finalization}),
            key=lambda item: item.value,
        )
    )
    if already_finalized:
        return ResolutionFinalityDecision(
            allowed=False,
            reason=FinalityReason.ALREADY_FINALIZED,
            finalized_resolution=evidence.requested_finalization,
            missing_finality_evidence=(),
            forbidden_finalizations=(),
            already_finalized_resolutions=already_finalized,
            locked_finality_violations=(),
        )

    locked_finality_violations = tuple(
        sorted(
            policy.locked_finality_resolutions
            & policy.mutation_resolutions
            & frozenset({evidence.requested_finalization}),
            key=lambda item: item.value,
        )
    )
    if locked_finality_violations:
        return ResolutionFinalityDecision(
            allowed=False,
            reason=FinalityReason.FINALITY_LOCK_VIOLATION,
            finalized_resolution=None,
            missing_finality_evidence=(),
            forbidden_finalizations=(),
            already_finalized_resolutions=(),
            locked_finality_violations=locked_finality_violations,
        )

    post_finalization_mutations = tuple(
        sorted(
            policy.already_finalized_resolutions
            & policy.mutation_resolutions,
            key=lambda item: item.value,
        )
    )
    if post_finalization_mutations:
        return ResolutionFinalityDecision(
            allowed=False,
            reason=FinalityReason.POST_FINALIZATION_MUTATION,
            finalized_resolution=None,
            missing_finality_evidence=(),
            forbidden_finalizations=(),
            already_finalized_resolutions=post_finalization_mutations,
            locked_finality_violations=(),
        )

    missing_finality_evidence = tuple(
        sorted(
            policy.required_finality_evidence
            - evidence.provided_finality_evidence,
            key=lambda item: item.value,
        )
    )
    if missing_finality_evidence:
        return ResolutionFinalityDecision(
            allowed=False,
            reason=FinalityReason.MISSING_FINALITY_EVIDENCE,
            finalized_resolution=None,
            missing_finality_evidence=missing_finality_evidence,
            forbidden_finalizations=(),
            already_finalized_resolutions=(),
            locked_finality_violations=(),
        )

    if (
        policy.requires_protection_continuity
        and not evidence.protection_continuity_proven
    ):
        return ResolutionFinalityDecision(
            allowed=False,
            reason=FinalityReason.PROTECTION_CONTINUITY_REQUIRED,
            finalized_resolution=None,
            missing_finality_evidence=(),
            forbidden_finalizations=(),
            already_finalized_resolutions=(),
            locked_finality_violations=(),
        )

    return ResolutionFinalityDecision(
        allowed=True,
        reason=FinalityReason.ALLOWED,
        finalized_resolution=evidence.requested_finalization,
        missing_finality_evidence=(),
        forbidden_finalizations=(),
        already_finalized_resolutions=(),
        locked_finality_violations=(),
    )
