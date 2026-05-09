from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Tuple


class RecoveryAction(str, Enum):
    NOOP = "NOOP"
    REPLAY_DECISION_TRACE = "REPLAY_DECISION_TRACE"
    RECONSTRUCT_SEMANTIC_STATE = "RECONSTRUCT_SEMANTIC_STATE"
    RESTORE_PROVISIONAL_PROTECTION = "RESTORE_PROVISIONAL_PROTECTION"
    RESTORE_AUTHORITATIVE_PROTECTION = "RESTORE_AUTHORITATIVE_PROTECTION"
    RETRY_CLEANUP_SEMANTICS = "RETRY_CLEANUP_SEMANTICS"
    REJECT_UNSAFE_RECOVERY = "REJECT_UNSAFE_RECOVERY"


class RecoveryBoundary(str, Enum):
    PRE_FINALITY = "PRE_FINALITY"
    POST_FINALITY = "POST_FINALITY"
    AUTHORITATIVE_BOUNDARY = "AUTHORITATIVE_BOUNDARY"
    PROVISIONAL_BOUNDARY = "PROVISIONAL_BOUNDARY"
    CLEANUP_BOUNDARY = "CLEANUP_BOUNDARY"
    AUDIT_REPLAY_BOUNDARY = "AUDIT_REPLAY_BOUNDARY"


class RecoveryEvidenceRequirement(str, Enum):
    DECISION_TRACE_PRESENT = "DECISION_TRACE_PRESENT"
    FINALITY_TRACE_PRESENT = "FINALITY_TRACE_PRESENT"
    AUTHORITATIVE_STATE_PRESENT = "AUTHORITATIVE_STATE_PRESENT"
    PROVISIONAL_STATE_PRESENT = "PROVISIONAL_STATE_PRESENT"
    PROTECTION_CONTINUITY_PROVEN = "PROTECTION_CONTINUITY_PROVEN"
    REPLAY_DETERMINISM_PROVEN = "REPLAY_DETERMINISM_PROVEN"


class RecoveryGovernanceReason(str, Enum):
    ALLOWED = "ALLOWED"
    FINALITY_SEMANTICS_NOT_ALLOWED = "FINALITY_SEMANTICS_NOT_ALLOWED"
    MISSING_RECOVERY_EVIDENCE = "MISSING_RECOVERY_EVIDENCE"
    FORBIDDEN_RECOVERY_ACTION = "FORBIDDEN_RECOVERY_ACTION"
    FORBIDDEN_RECOVERY_BOUNDARY = "FORBIDDEN_RECOVERY_BOUNDARY"
    IRREVERSIBLE_FINALITY_VIOLATION = "IRREVERSIBLE_FINALITY_VIOLATION"
    REPLAY_DETERMINISM_REQUIRED = "REPLAY_DETERMINISM_REQUIRED"
    PROTECTION_CONTINUITY_REQUIRED = "PROTECTION_CONTINUITY_REQUIRED"


@dataclass(frozen=True)
class SemanticRecoveryPolicy:
    allowed_recovery_actions: FrozenSet[RecoveryAction]
    forbidden_recovery_actions: FrozenSet[RecoveryAction]
    allowed_boundaries: FrozenSet[RecoveryBoundary]
    forbidden_boundaries: FrozenSet[RecoveryBoundary]
    required_recovery_evidence: FrozenSet[RecoveryEvidenceRequirement]
    irreversible_finality_boundaries: FrozenSet[RecoveryBoundary]
    replay_required: bool = True
    requires_protection_continuity: bool = True


@dataclass(frozen=True)
class SemanticRecoveryEvidence:
    requested_recovery_action: RecoveryAction
    requested_boundary: RecoveryBoundary
    provided_recovery_evidence: FrozenSet[RecoveryEvidenceRequirement]
    replay_determinism_proven: bool
    protection_continuity_proven: bool


@dataclass(frozen=True)
class SemanticRecoveryDecision:
    allowed: bool
    reason: RecoveryGovernanceReason
    recovery_action: RecoveryAction | None
    recovery_boundary: RecoveryBoundary | None
    missing_recovery_evidence: Tuple[RecoveryEvidenceRequirement, ...]
    forbidden_recovery_actions: Tuple[RecoveryAction, ...]
    forbidden_recovery_boundaries: Tuple[RecoveryBoundary, ...]
    irreversible_finality_violations: Tuple[RecoveryBoundary, ...]


def evaluate_semantic_recovery_governance(
    *,
    finality_semantics_allowed: bool,
    policy: SemanticRecoveryPolicy,
    evidence: SemanticRecoveryEvidence,
) -> SemanticRecoveryDecision:
    """
    Pure deterministic semantic recovery governance evaluator.

    This function does not recover runtime state.
    It does not retry orders, call broker APIs, call Binance APIs, persist,
    inspect DB state, inspect websocket state, use time, IO, randomness, or async.

    It only decides whether a semantic recovery action is admissible.
    """

    if not finality_semantics_allowed:
        return SemanticRecoveryDecision(
            allowed=False,
            reason=RecoveryGovernanceReason.FINALITY_SEMANTICS_NOT_ALLOWED,
            recovery_action=None,
            recovery_boundary=None,
            missing_recovery_evidence=(),
            forbidden_recovery_actions=(),
            forbidden_recovery_boundaries=(),
            irreversible_finality_violations=(),
        )

    if evidence.requested_recovery_action in policy.forbidden_recovery_actions:
        return SemanticRecoveryDecision(
            allowed=False,
            reason=RecoveryGovernanceReason.FORBIDDEN_RECOVERY_ACTION,
            recovery_action=None,
            recovery_boundary=evidence.requested_boundary,
            missing_recovery_evidence=(),
            forbidden_recovery_actions=(evidence.requested_recovery_action,),
            forbidden_recovery_boundaries=(),
            irreversible_finality_violations=(),
        )

    if evidence.requested_recovery_action not in policy.allowed_recovery_actions:
        return SemanticRecoveryDecision(
            allowed=False,
            reason=RecoveryGovernanceReason.FORBIDDEN_RECOVERY_ACTION,
            recovery_action=None,
            recovery_boundary=evidence.requested_boundary,
            missing_recovery_evidence=(),
            forbidden_recovery_actions=(evidence.requested_recovery_action,),
            forbidden_recovery_boundaries=(),
            irreversible_finality_violations=(),
        )

    if evidence.requested_boundary in policy.forbidden_boundaries:
        return SemanticRecoveryDecision(
            allowed=False,
            reason=RecoveryGovernanceReason.FORBIDDEN_RECOVERY_BOUNDARY,
            recovery_action=evidence.requested_recovery_action,
            recovery_boundary=None,
            missing_recovery_evidence=(),
            forbidden_recovery_actions=(),
            forbidden_recovery_boundaries=(evidence.requested_boundary,),
            irreversible_finality_violations=(),
        )

    if evidence.requested_boundary not in policy.allowed_boundaries:
        return SemanticRecoveryDecision(
            allowed=False,
            reason=RecoveryGovernanceReason.FORBIDDEN_RECOVERY_BOUNDARY,
            recovery_action=evidence.requested_recovery_action,
            recovery_boundary=None,
            missing_recovery_evidence=(),
            forbidden_recovery_actions=(),
            forbidden_recovery_boundaries=(evidence.requested_boundary,),
            irreversible_finality_violations=(),
        )

    irreversible_finality_violations = tuple(
        sorted(
            policy.irreversible_finality_boundaries
            & frozenset({evidence.requested_boundary}),
            key=lambda item: item.value,
        )
    )
    if irreversible_finality_violations:
        return SemanticRecoveryDecision(
            allowed=False,
            reason=RecoveryGovernanceReason.IRREVERSIBLE_FINALITY_VIOLATION,
            recovery_action=evidence.requested_recovery_action,
            recovery_boundary=evidence.requested_boundary,
            missing_recovery_evidence=(),
            forbidden_recovery_actions=(),
            forbidden_recovery_boundaries=(),
            irreversible_finality_violations=irreversible_finality_violations,
        )

    missing_recovery_evidence = tuple(
        sorted(
            policy.required_recovery_evidence - evidence.provided_recovery_evidence,
            key=lambda item: item.value,
        )
    )
    if missing_recovery_evidence:
        return SemanticRecoveryDecision(
            allowed=False,
            reason=RecoveryGovernanceReason.MISSING_RECOVERY_EVIDENCE,
            recovery_action=evidence.requested_recovery_action,
            recovery_boundary=evidence.requested_boundary,
            missing_recovery_evidence=missing_recovery_evidence,
            forbidden_recovery_actions=(),
            forbidden_recovery_boundaries=(),
            irreversible_finality_violations=(),
        )

    if policy.replay_required and not evidence.replay_determinism_proven:
        return SemanticRecoveryDecision(
            allowed=False,
            reason=RecoveryGovernanceReason.REPLAY_DETERMINISM_REQUIRED,
            recovery_action=evidence.requested_recovery_action,
            recovery_boundary=evidence.requested_boundary,
            missing_recovery_evidence=(),
            forbidden_recovery_actions=(),
            forbidden_recovery_boundaries=(),
            irreversible_finality_violations=(),
        )

    if (
        policy.requires_protection_continuity
        and not evidence.protection_continuity_proven
    ):
        return SemanticRecoveryDecision(
            allowed=False,
            reason=RecoveryGovernanceReason.PROTECTION_CONTINUITY_REQUIRED,
            recovery_action=evidence.requested_recovery_action,
            recovery_boundary=evidence.requested_boundary,
            missing_recovery_evidence=(),
            forbidden_recovery_actions=(),
            forbidden_recovery_boundaries=(),
            irreversible_finality_violations=(),
        )

    return SemanticRecoveryDecision(
        allowed=True,
        reason=RecoveryGovernanceReason.ALLOWED,
        recovery_action=evidence.requested_recovery_action,
        recovery_boundary=evidence.requested_boundary,
        missing_recovery_evidence=(),
        forbidden_recovery_actions=(),
        forbidden_recovery_boundaries=(),
        irreversible_finality_violations=(),
    )
