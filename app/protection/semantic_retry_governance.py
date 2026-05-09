from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Tuple


class RetryAction(str, Enum):
    NOOP = "NOOP"
    RETRY_RECONCILIATION = "RETRY_RECONCILIATION"
    RETRY_CLEANUP = "RETRY_CLEANUP"
    RETRY_AUDIT_REPLAY = "RETRY_AUDIT_REPLAY"
    RETRY_CONVERGENCE_VALIDATION = "RETRY_CONVERGENCE_VALIDATION"
    REJECT_UNSAFE_RETRY = "REJECT_UNSAFE_RETRY"


class RetryBoundary(str, Enum):
    PRE_FINALITY = "PRE_FINALITY"
    POST_FINALITY = "POST_FINALITY"
    CLEANUP_BOUNDARY = "CLEANUP_BOUNDARY"
    CONVERGENCE_BOUNDARY = "CONVERGENCE_BOUNDARY"
    AUDIT_REPLAY_BOUNDARY = "AUDIT_REPLAY_BOUNDARY"


class RetryEvidenceRequirement(str, Enum):
    RETRY_TRACE_PRESENT = "RETRY_TRACE_PRESENT"
    IDEMPOTENCY_PROVEN = "IDEMPOTENCY_PROVEN"
    REPLAY_DETERMINISM_PROVEN = "REPLAY_DETERMINISM_PROVEN"
    CONVERGENCE_STATE_PRESENT = "CONVERGENCE_STATE_PRESENT"
    PROTECTION_CONTINUITY_PROVEN = "PROTECTION_CONTINUITY_PROVEN"


class RetryGovernanceReason(str, Enum):
    ALLOWED = "ALLOWED"
    RECOVERY_GOVERNANCE_NOT_ALLOWED = (
        "RECOVERY_GOVERNANCE_NOT_ALLOWED"
    )
    MISSING_RETRY_EVIDENCE = "MISSING_RETRY_EVIDENCE"
    FORBIDDEN_RETRY_ACTION = "FORBIDDEN_RETRY_ACTION"
    FORBIDDEN_RETRY_BOUNDARY = "FORBIDDEN_RETRY_BOUNDARY"
    IDEMPOTENCY_REQUIRED = "IDEMPOTENCY_REQUIRED"
    REPLAY_DETERMINISM_REQUIRED = (
        "REPLAY_DETERMINISM_REQUIRED"
    )
    PROTECTION_CONTINUITY_REQUIRED = (
        "PROTECTION_CONTINUITY_REQUIRED"
    )
    POST_FINALITY_RETRY_VIOLATION = (
        "POST_FINALITY_RETRY_VIOLATION"
    )


@dataclass(frozen=True)
class SemanticRetryPolicy:
    allowed_retry_actions: FrozenSet[RetryAction]
    forbidden_retry_actions: FrozenSet[RetryAction]
    allowed_boundaries: FrozenSet[RetryBoundary]
    forbidden_boundaries: FrozenSet[RetryBoundary]
    required_retry_evidence: FrozenSet[RetryEvidenceRequirement]
    post_finality_forbidden_boundaries: FrozenSet[RetryBoundary]
    idempotency_required: bool = True
    replay_required: bool = True
    requires_protection_continuity: bool = True


@dataclass(frozen=True)
class SemanticRetryEvidence:
    requested_retry_action: RetryAction
    requested_boundary: RetryBoundary
    provided_retry_evidence: FrozenSet[RetryEvidenceRequirement]
    idempotency_proven: bool
    replay_determinism_proven: bool
    protection_continuity_proven: bool


@dataclass(frozen=True)
class SemanticRetryDecision:
    allowed: bool
    reason: RetryGovernanceReason
    retry_action: RetryAction | None
    retry_boundary: RetryBoundary | None
    missing_retry_evidence: Tuple[
        RetryEvidenceRequirement,
        ...
    ]
    forbidden_retry_actions: Tuple[RetryAction, ...]
    forbidden_retry_boundaries: Tuple[
        RetryBoundary,
        ...
    ]
    post_finality_retry_violations: Tuple[
        RetryBoundary,
        ...
    ]


def evaluate_semantic_retry_governance(
    *,
    recovery_governance_allowed: bool,
    policy: SemanticRetryPolicy,
    evidence: SemanticRetryEvidence,
) -> SemanticRetryDecision:
    """
    Pure deterministic semantic retry governance evaluator.

    This function does not execute retries.
    It does not schedule retry loops, call broker APIs,
    call Binance APIs, inspect DB state,
    inspect websocket state, use time, IO,
    randomness, or async orchestration.

    It only evaluates retry semantic admissibility.
    """

    if not recovery_governance_allowed:
        return SemanticRetryDecision(
            allowed=False,
            reason=RetryGovernanceReason.RECOVERY_GOVERNANCE_NOT_ALLOWED,
            retry_action=None,
            retry_boundary=None,
            missing_retry_evidence=(),
            forbidden_retry_actions=(),
            forbidden_retry_boundaries=(),
            post_finality_retry_violations=(),
        )

    if evidence.requested_retry_action in policy.forbidden_retry_actions:
        return SemanticRetryDecision(
            allowed=False,
            reason=RetryGovernanceReason.FORBIDDEN_RETRY_ACTION,
            retry_action=None,
            retry_boundary=evidence.requested_boundary,
            missing_retry_evidence=(),
            forbidden_retry_actions=(
                evidence.requested_retry_action,
            ),
            forbidden_retry_boundaries=(),
            post_finality_retry_violations=(),
        )

    if (
        evidence.requested_retry_action
        not in policy.allowed_retry_actions
    ):
        return SemanticRetryDecision(
            allowed=False,
            reason=RetryGovernanceReason.FORBIDDEN_RETRY_ACTION,
            retry_action=None,
            retry_boundary=evidence.requested_boundary,
            missing_retry_evidence=(),
            forbidden_retry_actions=(
                evidence.requested_retry_action,
            ),
            forbidden_retry_boundaries=(),
            post_finality_retry_violations=(),
        )

    if evidence.requested_boundary in policy.forbidden_boundaries:
        return SemanticRetryDecision(
            allowed=False,
            reason=RetryGovernanceReason.FORBIDDEN_RETRY_BOUNDARY,
            retry_action=evidence.requested_retry_action,
            retry_boundary=None,
            missing_retry_evidence=(),
            forbidden_retry_actions=(),
            forbidden_retry_boundaries=(
                evidence.requested_boundary,
            ),
            post_finality_retry_violations=(),
        )

    if evidence.requested_boundary not in policy.allowed_boundaries:
        return SemanticRetryDecision(
            allowed=False,
            reason=RetryGovernanceReason.FORBIDDEN_RETRY_BOUNDARY,
            retry_action=evidence.requested_retry_action,
            retry_boundary=None,
            missing_retry_evidence=(),
            forbidden_retry_actions=(),
            forbidden_retry_boundaries=(
                evidence.requested_boundary,
            ),
            post_finality_retry_violations=(),
        )

    post_finality_retry_violations = tuple(
        sorted(
            policy.post_finality_forbidden_boundaries
            & frozenset({evidence.requested_boundary}),
            key=lambda item: item.value,
        )
    )
    if post_finality_retry_violations:
        return SemanticRetryDecision(
            allowed=False,
            reason=RetryGovernanceReason.POST_FINALITY_RETRY_VIOLATION,
            retry_action=evidence.requested_retry_action,
            retry_boundary=evidence.requested_boundary,
            missing_retry_evidence=(),
            forbidden_retry_actions=(),
            forbidden_retry_boundaries=(),
            post_finality_retry_violations=(
                post_finality_retry_violations
            ),
        )

    missing_retry_evidence = tuple(
        sorted(
            policy.required_retry_evidence
            - evidence.provided_retry_evidence,
            key=lambda item: item.value,
        )
    )
    if missing_retry_evidence:
        return SemanticRetryDecision(
            allowed=False,
            reason=RetryGovernanceReason.MISSING_RETRY_EVIDENCE,
            retry_action=evidence.requested_retry_action,
            retry_boundary=evidence.requested_boundary,
            missing_retry_evidence=missing_retry_evidence,
            forbidden_retry_actions=(),
            forbidden_retry_boundaries=(),
            post_finality_retry_violations=(),
        )

    if (
        policy.idempotency_required
        and not evidence.idempotency_proven
    ):
        return SemanticRetryDecision(
            allowed=False,
            reason=RetryGovernanceReason.IDEMPOTENCY_REQUIRED,
            retry_action=evidence.requested_retry_action,
            retry_boundary=evidence.requested_boundary,
            missing_retry_evidence=(),
            forbidden_retry_actions=(),
            forbidden_retry_boundaries=(),
            post_finality_retry_violations=(),
        )

    if (
        policy.replay_required
        and not evidence.replay_determinism_proven
    ):
        return SemanticRetryDecision(
            allowed=False,
            reason=RetryGovernanceReason.REPLAY_DETERMINISM_REQUIRED,
            retry_action=evidence.requested_retry_action,
            retry_boundary=evidence.requested_boundary,
            missing_retry_evidence=(),
            forbidden_retry_actions=(),
            forbidden_retry_boundaries=(),
            post_finality_retry_violations=(),
        )

    if (
        policy.requires_protection_continuity
        and not evidence.protection_continuity_proven
    ):
        return SemanticRetryDecision(
            allowed=False,
            reason=RetryGovernanceReason.PROTECTION_CONTINUITY_REQUIRED,
            retry_action=evidence.requested_retry_action,
            retry_boundary=evidence.requested_boundary,
            missing_retry_evidence=(),
            forbidden_retry_actions=(),
            forbidden_retry_boundaries=(),
            post_finality_retry_violations=(),
        )

    return SemanticRetryDecision(
        allowed=True,
        reason=RetryGovernanceReason.ALLOWED,
        retry_action=evidence.requested_retry_action,
        retry_boundary=evidence.requested_boundary,
        missing_retry_evidence=(),
        forbidden_retry_actions=(),
        forbidden_retry_boundaries=(),
        post_finality_retry_violations=(),
    )
