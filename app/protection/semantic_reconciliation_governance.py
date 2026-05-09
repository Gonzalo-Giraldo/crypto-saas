from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Tuple


class ReconciliationMode(str, Enum):
    NOOP = "NOOP"
    AUTHORITATIVE_RECONCILIATION = "AUTHORITATIVE_RECONCILIATION"
    EQUIVALENT_RECONCILIATION = "EQUIVALENT_RECONCILIATION"
    REPLACEMENT_RECONCILIATION = "REPLACEMENT_RECONCILIATION"
    CLEANUP_RECONCILIATION = "CLEANUP_RECONCILIATION"
    TRAILING_RECONCILIATION = "TRAILING_RECONCILIATION"
    AUDIT_RECONCILIATION = "AUDIT_RECONCILIATION"


class ReconciliationEvidenceRequirement(str, Enum):
    AUTHORITATIVE_EXIT_PRESENT = "AUTHORITATIVE_EXIT_PRESENT"
    PROVISIONAL_EXIT_PRESENT = "PROVISIONAL_EXIT_PRESENT"
    MATCHED_RECONCILIATION_PROOF = "MATCHED_RECONCILIATION_PROOF"
    EQUIVALENCE_PROOF = "EQUIVALENCE_PROOF"
    REPLACEMENT_PROOF = "REPLACEMENT_PROOF"
    CLEANUP_PROOF = "CLEANUP_PROOF"
    TRAILING_BASELINE_PROOF = "TRAILING_BASELINE_PROOF"
    AUDIT_TRACE_PRESENT = "AUDIT_TRACE_PRESENT"
    PROTECTION_CONTINUITY_PROVEN = "PROTECTION_CONTINUITY_PROVEN"
    REPLAY_DETERMINISM_PROVEN = "REPLAY_DETERMINISM_PROVEN"


class ReconciliationBoundary(str, Enum):
    AUTHORITATIVE_BOUNDARY = "AUTHORITATIVE_BOUNDARY"
    EQUIVALENT_BOUNDARY = "EQUIVALENT_BOUNDARY"
    REPLACEMENT_BOUNDARY = "REPLACEMENT_BOUNDARY"
    CLEANUP_BOUNDARY = "CLEANUP_BOUNDARY"
    TRAILING_BOUNDARY = "TRAILING_BOUNDARY"
    AUDIT_BOUNDARY = "AUDIT_BOUNDARY"


class ReconciliationGovernanceReason(str, Enum):
    ALLOWED = "ALLOWED"
    RETRY_GOVERNANCE_NOT_ALLOWED = "RETRY_GOVERNANCE_NOT_ALLOWED"
    MISSING_RECONCILIATION_EVIDENCE = "MISSING_RECONCILIATION_EVIDENCE"
    FORBIDDEN_RECONCILIATION_MODE = "FORBIDDEN_RECONCILIATION_MODE"
    FORBIDDEN_RECONCILIATION_BOUNDARY = "FORBIDDEN_RECONCILIATION_BOUNDARY"
    RECONCILIATION_MODE_BOUNDARY_MISMATCH = (
        "RECONCILIATION_MODE_BOUNDARY_MISMATCH"
    )
    RECONCILIATION_CLOSURE_REQUIRED = "RECONCILIATION_CLOSURE_REQUIRED"
    REPLAY_DETERMINISM_REQUIRED = "REPLAY_DETERMINISM_REQUIRED"
    PROTECTION_CONTINUITY_REQUIRED = "PROTECTION_CONTINUITY_REQUIRED"


@dataclass(frozen=True)
class ReconciliationModeBoundaryRule:
    mode: ReconciliationMode
    boundary: ReconciliationBoundary


@dataclass(frozen=True)
class SemanticReconciliationPolicy:
    allowed_modes: FrozenSet[ReconciliationMode]
    forbidden_modes: FrozenSet[ReconciliationMode]
    allowed_boundaries: FrozenSet[ReconciliationBoundary]
    forbidden_boundaries: FrozenSet[ReconciliationBoundary]
    required_reconciliation_evidence: FrozenSet[
        ReconciliationEvidenceRequirement
    ]
    mode_boundary_rules: FrozenSet[ReconciliationModeBoundaryRule]
    closure_required_modes: FrozenSet[ReconciliationMode]
    replay_required: bool = True
    requires_protection_continuity: bool = True


@dataclass(frozen=True)
class SemanticReconciliationEvidence:
    requested_mode: ReconciliationMode
    requested_boundary: ReconciliationBoundary
    provided_reconciliation_evidence: FrozenSet[
        ReconciliationEvidenceRequirement
    ]
    reconciliation_closure_proven: bool
    replay_determinism_proven: bool
    protection_continuity_proven: bool


@dataclass(frozen=True)
class SemanticReconciliationDecision:
    allowed: bool
    reason: ReconciliationGovernanceReason
    reconciliation_mode: ReconciliationMode | None
    reconciliation_boundary: ReconciliationBoundary | None
    missing_reconciliation_evidence: Tuple[
        ReconciliationEvidenceRequirement,
        ...
    ]
    forbidden_modes: Tuple[ReconciliationMode, ...]
    forbidden_boundaries: Tuple[ReconciliationBoundary, ...]
    mode_boundary_violations: Tuple[
        ReconciliationModeBoundaryRule,
        ...
    ]


def evaluate_semantic_reconciliation_governance(
    *,
    retry_governance_allowed: bool,
    policy: SemanticReconciliationPolicy,
    evidence: SemanticReconciliationEvidence,
) -> SemanticReconciliationDecision:
    """
    Pure deterministic semantic reconciliation governance evaluator.

    This function does not reconcile runtime state.
    It does not inspect websocket state, call broker APIs, call Binance APIs,
    inspect DB state, use time, IO, randomness, or async orchestration.

    It only decides whether semantic reconciliation is admissible.
    """

    if not retry_governance_allowed:
        return SemanticReconciliationDecision(
            allowed=False,
            reason=ReconciliationGovernanceReason.RETRY_GOVERNANCE_NOT_ALLOWED,
            reconciliation_mode=None,
            reconciliation_boundary=None,
            missing_reconciliation_evidence=(),
            forbidden_modes=(),
            forbidden_boundaries=(),
            mode_boundary_violations=(),
        )

    if evidence.requested_mode in policy.forbidden_modes:
        return SemanticReconciliationDecision(
            allowed=False,
            reason=ReconciliationGovernanceReason.FORBIDDEN_RECONCILIATION_MODE,
            reconciliation_mode=None,
            reconciliation_boundary=evidence.requested_boundary,
            missing_reconciliation_evidence=(),
            forbidden_modes=(evidence.requested_mode,),
            forbidden_boundaries=(),
            mode_boundary_violations=(),
        )

    if evidence.requested_mode not in policy.allowed_modes:
        return SemanticReconciliationDecision(
            allowed=False,
            reason=ReconciliationGovernanceReason.FORBIDDEN_RECONCILIATION_MODE,
            reconciliation_mode=None,
            reconciliation_boundary=evidence.requested_boundary,
            missing_reconciliation_evidence=(),
            forbidden_modes=(evidence.requested_mode,),
            forbidden_boundaries=(),
            mode_boundary_violations=(),
        )

    if evidence.requested_boundary in policy.forbidden_boundaries:
        return SemanticReconciliationDecision(
            allowed=False,
            reason=ReconciliationGovernanceReason.FORBIDDEN_RECONCILIATION_BOUNDARY,
            reconciliation_mode=evidence.requested_mode,
            reconciliation_boundary=None,
            missing_reconciliation_evidence=(),
            forbidden_modes=(),
            forbidden_boundaries=(evidence.requested_boundary,),
            mode_boundary_violations=(),
        )

    if evidence.requested_boundary not in policy.allowed_boundaries:
        return SemanticReconciliationDecision(
            allowed=False,
            reason=ReconciliationGovernanceReason.FORBIDDEN_RECONCILIATION_BOUNDARY,
            reconciliation_mode=evidence.requested_mode,
            reconciliation_boundary=None,
            missing_reconciliation_evidence=(),
            forbidden_modes=(),
            forbidden_boundaries=(evidence.requested_boundary,),
            mode_boundary_violations=(),
        )

    mode_boundary_violations = tuple(
        sorted(
            (
                rule
                for rule in policy.mode_boundary_rules
                if rule.mode == evidence.requested_mode
                and rule.boundary != evidence.requested_boundary
            ),
            key=lambda item: (item.mode.value, item.boundary.value),
        )
    )
    if mode_boundary_violations:
        return SemanticReconciliationDecision(
            allowed=False,
            reason=ReconciliationGovernanceReason.RECONCILIATION_MODE_BOUNDARY_MISMATCH,
            reconciliation_mode=evidence.requested_mode,
            reconciliation_boundary=evidence.requested_boundary,
            missing_reconciliation_evidence=(),
            forbidden_modes=(),
            forbidden_boundaries=(),
            mode_boundary_violations=mode_boundary_violations,
        )

    missing_reconciliation_evidence = tuple(
        sorted(
            policy.required_reconciliation_evidence
            - evidence.provided_reconciliation_evidence,
            key=lambda item: item.value,
        )
    )
    if missing_reconciliation_evidence:
        return SemanticReconciliationDecision(
            allowed=False,
            reason=ReconciliationGovernanceReason.MISSING_RECONCILIATION_EVIDENCE,
            reconciliation_mode=evidence.requested_mode,
            reconciliation_boundary=evidence.requested_boundary,
            missing_reconciliation_evidence=missing_reconciliation_evidence,
            forbidden_modes=(),
            forbidden_boundaries=(),
            mode_boundary_violations=(),
        )

    if (
        evidence.requested_mode in policy.closure_required_modes
        and not evidence.reconciliation_closure_proven
    ):
        return SemanticReconciliationDecision(
            allowed=False,
            reason=ReconciliationGovernanceReason.RECONCILIATION_CLOSURE_REQUIRED,
            reconciliation_mode=evidence.requested_mode,
            reconciliation_boundary=evidence.requested_boundary,
            missing_reconciliation_evidence=(),
            forbidden_modes=(),
            forbidden_boundaries=(),
            mode_boundary_violations=(),
        )

    if policy.replay_required and not evidence.replay_determinism_proven:
        return SemanticReconciliationDecision(
            allowed=False,
            reason=ReconciliationGovernanceReason.REPLAY_DETERMINISM_REQUIRED,
            reconciliation_mode=evidence.requested_mode,
            reconciliation_boundary=evidence.requested_boundary,
            missing_reconciliation_evidence=(),
            forbidden_modes=(),
            forbidden_boundaries=(),
            mode_boundary_violations=(),
        )

    if (
        policy.requires_protection_continuity
        and not evidence.protection_continuity_proven
    ):
        return SemanticReconciliationDecision(
            allowed=False,
            reason=ReconciliationGovernanceReason.PROTECTION_CONTINUITY_REQUIRED,
            reconciliation_mode=evidence.requested_mode,
            reconciliation_boundary=evidence.requested_boundary,
            missing_reconciliation_evidence=(),
            forbidden_modes=(),
            forbidden_boundaries=(),
            mode_boundary_violations=(),
        )

    return SemanticReconciliationDecision(
        allowed=True,
        reason=ReconciliationGovernanceReason.ALLOWED,
        reconciliation_mode=evidence.requested_mode,
        reconciliation_boundary=evidence.requested_boundary,
        missing_reconciliation_evidence=(),
        forbidden_modes=(),
        forbidden_boundaries=(),
        mode_boundary_violations=(),
    )
