from app.protection.semantic_recovery_governance import (
    RecoveryAction,
    RecoveryBoundary,
    RecoveryEvidenceRequirement,
    RecoveryGovernanceReason,
    SemanticRecoveryDecision,
    SemanticRecoveryEvidence,
    SemanticRecoveryPolicy,
    evaluate_semantic_recovery_governance,
)


def test_denies_when_finality_semantics_not_allowed():
    decision = evaluate_semantic_recovery_governance(
        finality_semantics_allowed=False,
        policy=SemanticRecoveryPolicy(
            allowed_recovery_actions=frozenset({RecoveryAction.NOOP}),
            forbidden_recovery_actions=frozenset(),
            allowed_boundaries=frozenset({RecoveryBoundary.AUDIT_REPLAY_BOUNDARY}),
            forbidden_boundaries=frozenset(),
            required_recovery_evidence=frozenset(),
            irreversible_finality_boundaries=frozenset(),
        ),
        evidence=SemanticRecoveryEvidence(
            requested_recovery_action=RecoveryAction.NOOP,
            requested_boundary=RecoveryBoundary.AUDIT_REPLAY_BOUNDARY,
            provided_recovery_evidence=frozenset(),
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == RecoveryGovernanceReason.FINALITY_SEMANTICS_NOT_ALLOWED


def test_denies_forbidden_recovery_action():
    decision = evaluate_semantic_recovery_governance(
        finality_semantics_allowed=True,
        policy=SemanticRecoveryPolicy(
            allowed_recovery_actions=frozenset(
                {RecoveryAction.RECONSTRUCT_SEMANTIC_STATE}
            ),
            forbidden_recovery_actions=frozenset(
                {RecoveryAction.RESTORE_PROVISIONAL_PROTECTION}
            ),
            allowed_boundaries=frozenset({RecoveryBoundary.PRE_FINALITY}),
            forbidden_boundaries=frozenset(),
            required_recovery_evidence=frozenset(),
            irreversible_finality_boundaries=frozenset(),
        ),
        evidence=SemanticRecoveryEvidence(
            requested_recovery_action=RecoveryAction.RESTORE_PROVISIONAL_PROTECTION,
            requested_boundary=RecoveryBoundary.PRE_FINALITY,
            provided_recovery_evidence=frozenset(),
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == RecoveryGovernanceReason.FORBIDDEN_RECOVERY_ACTION
    assert decision.forbidden_recovery_actions == (
        RecoveryAction.RESTORE_PROVISIONAL_PROTECTION,
    )


def test_denies_non_allowed_recovery_action():
    decision = evaluate_semantic_recovery_governance(
        finality_semantics_allowed=True,
        policy=SemanticRecoveryPolicy(
            allowed_recovery_actions=frozenset({RecoveryAction.REPLAY_DECISION_TRACE}),
            forbidden_recovery_actions=frozenset(),
            allowed_boundaries=frozenset({RecoveryBoundary.AUDIT_REPLAY_BOUNDARY}),
            forbidden_boundaries=frozenset(),
            required_recovery_evidence=frozenset(),
            irreversible_finality_boundaries=frozenset(),
        ),
        evidence=SemanticRecoveryEvidence(
            requested_recovery_action=RecoveryAction.RESTORE_AUTHORITATIVE_PROTECTION,
            requested_boundary=RecoveryBoundary.AUDIT_REPLAY_BOUNDARY,
            provided_recovery_evidence=frozenset(),
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == RecoveryGovernanceReason.FORBIDDEN_RECOVERY_ACTION


def test_denies_forbidden_recovery_boundary():
    decision = evaluate_semantic_recovery_governance(
        finality_semantics_allowed=True,
        policy=SemanticRecoveryPolicy(
            allowed_recovery_actions=frozenset(
                {RecoveryAction.RECONSTRUCT_SEMANTIC_STATE}
            ),
            forbidden_recovery_actions=frozenset(),
            allowed_boundaries=frozenset({RecoveryBoundary.PRE_FINALITY}),
            forbidden_boundaries=frozenset({RecoveryBoundary.POST_FINALITY}),
            required_recovery_evidence=frozenset(),
            irreversible_finality_boundaries=frozenset(),
        ),
        evidence=SemanticRecoveryEvidence(
            requested_recovery_action=RecoveryAction.RECONSTRUCT_SEMANTIC_STATE,
            requested_boundary=RecoveryBoundary.POST_FINALITY,
            provided_recovery_evidence=frozenset(),
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == RecoveryGovernanceReason.FORBIDDEN_RECOVERY_BOUNDARY
    assert decision.forbidden_recovery_boundaries == (
        RecoveryBoundary.POST_FINALITY,
    )


def test_denies_irreversible_finality_boundary_violation():
    decision = evaluate_semantic_recovery_governance(
        finality_semantics_allowed=True,
        policy=SemanticRecoveryPolicy(
            allowed_recovery_actions=frozenset(
                {RecoveryAction.RECONSTRUCT_SEMANTIC_STATE}
            ),
            forbidden_recovery_actions=frozenset(),
            allowed_boundaries=frozenset({RecoveryBoundary.POST_FINALITY}),
            forbidden_boundaries=frozenset(),
            required_recovery_evidence=frozenset(),
            irreversible_finality_boundaries=frozenset(
                {RecoveryBoundary.POST_FINALITY}
            ),
        ),
        evidence=SemanticRecoveryEvidence(
            requested_recovery_action=RecoveryAction.RECONSTRUCT_SEMANTIC_STATE,
            requested_boundary=RecoveryBoundary.POST_FINALITY,
            provided_recovery_evidence=frozenset(),
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == RecoveryGovernanceReason.IRREVERSIBLE_FINALITY_VIOLATION
    )


def test_denies_missing_recovery_evidence():
    decision = evaluate_semantic_recovery_governance(
        finality_semantics_allowed=True,
        policy=SemanticRecoveryPolicy(
            allowed_recovery_actions=frozenset(
                {RecoveryAction.REPLAY_DECISION_TRACE}
            ),
            forbidden_recovery_actions=frozenset(),
            allowed_boundaries=frozenset({RecoveryBoundary.AUDIT_REPLAY_BOUNDARY}),
            forbidden_boundaries=frozenset(),
            required_recovery_evidence=frozenset(
                {
                    RecoveryEvidenceRequirement.DECISION_TRACE_PRESENT,
                    RecoveryEvidenceRequirement.REPLAY_DETERMINISM_PROVEN,
                }
            ),
            irreversible_finality_boundaries=frozenset(),
        ),
        evidence=SemanticRecoveryEvidence(
            requested_recovery_action=RecoveryAction.REPLAY_DECISION_TRACE,
            requested_boundary=RecoveryBoundary.AUDIT_REPLAY_BOUNDARY,
            provided_recovery_evidence=frozenset(
                {RecoveryEvidenceRequirement.DECISION_TRACE_PRESENT}
            ),
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == RecoveryGovernanceReason.MISSING_RECOVERY_EVIDENCE
    assert decision.missing_recovery_evidence == (
        RecoveryEvidenceRequirement.REPLAY_DETERMINISM_PROVEN,
    )


def test_denies_when_replay_determinism_not_proven():
    decision = evaluate_semantic_recovery_governance(
        finality_semantics_allowed=True,
        policy=SemanticRecoveryPolicy(
            allowed_recovery_actions=frozenset(
                {RecoveryAction.REPLAY_DECISION_TRACE}
            ),
            forbidden_recovery_actions=frozenset(),
            allowed_boundaries=frozenset({RecoveryBoundary.AUDIT_REPLAY_BOUNDARY}),
            forbidden_boundaries=frozenset(),
            required_recovery_evidence=frozenset(),
            irreversible_finality_boundaries=frozenset(),
            replay_required=True,
        ),
        evidence=SemanticRecoveryEvidence(
            requested_recovery_action=RecoveryAction.REPLAY_DECISION_TRACE,
            requested_boundary=RecoveryBoundary.AUDIT_REPLAY_BOUNDARY,
            provided_recovery_evidence=frozenset(),
            replay_determinism_proven=False,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == RecoveryGovernanceReason.REPLAY_DETERMINISM_REQUIRED


def test_denies_when_protection_continuity_not_proven():
    decision = evaluate_semantic_recovery_governance(
        finality_semantics_allowed=True,
        policy=SemanticRecoveryPolicy(
            allowed_recovery_actions=frozenset(
                {RecoveryAction.RECONSTRUCT_SEMANTIC_STATE}
            ),
            forbidden_recovery_actions=frozenset(),
            allowed_boundaries=frozenset({RecoveryBoundary.PRE_FINALITY}),
            forbidden_boundaries=frozenset(),
            required_recovery_evidence=frozenset(),
            irreversible_finality_boundaries=frozenset(),
            requires_protection_continuity=True,
        ),
        evidence=SemanticRecoveryEvidence(
            requested_recovery_action=RecoveryAction.RECONSTRUCT_SEMANTIC_STATE,
            requested_boundary=RecoveryBoundary.PRE_FINALITY,
            provided_recovery_evidence=frozenset(),
            replay_determinism_proven=True,
            protection_continuity_proven=False,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == RecoveryGovernanceReason.PROTECTION_CONTINUITY_REQUIRED


def test_authorizes_recovery_when_governance_is_satisfied():
    decision = evaluate_semantic_recovery_governance(
        finality_semantics_allowed=True,
        policy=SemanticRecoveryPolicy(
            allowed_recovery_actions=frozenset(
                {
                    RecoveryAction.REPLAY_DECISION_TRACE,
                    RecoveryAction.RECONSTRUCT_SEMANTIC_STATE,
                }
            ),
            forbidden_recovery_actions=frozenset(),
            allowed_boundaries=frozenset({RecoveryBoundary.AUDIT_REPLAY_BOUNDARY}),
            forbidden_boundaries=frozenset(),
            required_recovery_evidence=frozenset(
                {
                    RecoveryEvidenceRequirement.DECISION_TRACE_PRESENT,
                    RecoveryEvidenceRequirement.FINALITY_TRACE_PRESENT,
                    RecoveryEvidenceRequirement.REPLAY_DETERMINISM_PROVEN,
                    RecoveryEvidenceRequirement.PROTECTION_CONTINUITY_PROVEN,
                }
            ),
            irreversible_finality_boundaries=frozenset(),
            replay_required=True,
            requires_protection_continuity=True,
        ),
        evidence=SemanticRecoveryEvidence(
            requested_recovery_action=RecoveryAction.REPLAY_DECISION_TRACE,
            requested_boundary=RecoveryBoundary.AUDIT_REPLAY_BOUNDARY,
            provided_recovery_evidence=frozenset(
                {
                    RecoveryEvidenceRequirement.DECISION_TRACE_PRESENT,
                    RecoveryEvidenceRequirement.FINALITY_TRACE_PRESENT,
                    RecoveryEvidenceRequirement.REPLAY_DETERMINISM_PROVEN,
                    RecoveryEvidenceRequirement.PROTECTION_CONTINUITY_PROVEN,
                }
            ),
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert isinstance(decision, SemanticRecoveryDecision)
    assert decision.allowed is True
    assert decision.reason == RecoveryGovernanceReason.ALLOWED
    assert decision.recovery_action == RecoveryAction.REPLAY_DECISION_TRACE
    assert decision.recovery_boundary == RecoveryBoundary.AUDIT_REPLAY_BOUNDARY
