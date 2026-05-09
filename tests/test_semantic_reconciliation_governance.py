from app.protection.semantic_reconciliation_governance import (
    ReconciliationBoundary,
    ReconciliationEvidenceRequirement,
    ReconciliationGovernanceReason,
    ReconciliationMode,
    ReconciliationModeBoundaryRule,
    SemanticReconciliationDecision,
    SemanticReconciliationEvidence,
    SemanticReconciliationPolicy,
    evaluate_semantic_reconciliation_governance,
)


def test_denies_when_retry_governance_not_allowed():
    decision = evaluate_semantic_reconciliation_governance(
        retry_governance_allowed=False,
        policy=SemanticReconciliationPolicy(
            allowed_modes=frozenset({ReconciliationMode.NOOP}),
            forbidden_modes=frozenset(),
            allowed_boundaries=frozenset({ReconciliationBoundary.AUDIT_BOUNDARY}),
            forbidden_boundaries=frozenset(),
            required_reconciliation_evidence=frozenset(),
            mode_boundary_rules=frozenset(),
            closure_required_modes=frozenset(),
        ),
        evidence=SemanticReconciliationEvidence(
            requested_mode=ReconciliationMode.NOOP,
            requested_boundary=ReconciliationBoundary.AUDIT_BOUNDARY,
            provided_reconciliation_evidence=frozenset(),
            reconciliation_closure_proven=True,
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == ReconciliationGovernanceReason.RETRY_GOVERNANCE_NOT_ALLOWED
    )


def test_denies_forbidden_reconciliation_mode():
    decision = evaluate_semantic_reconciliation_governance(
        retry_governance_allowed=True,
        policy=SemanticReconciliationPolicy(
            allowed_modes=frozenset({ReconciliationMode.AUDIT_RECONCILIATION}),
            forbidden_modes=frozenset({ReconciliationMode.REPLACEMENT_RECONCILIATION}),
            allowed_boundaries=frozenset({ReconciliationBoundary.REPLACEMENT_BOUNDARY}),
            forbidden_boundaries=frozenset(),
            required_reconciliation_evidence=frozenset(),
            mode_boundary_rules=frozenset(),
            closure_required_modes=frozenset(),
        ),
        evidence=SemanticReconciliationEvidence(
            requested_mode=ReconciliationMode.REPLACEMENT_RECONCILIATION,
            requested_boundary=ReconciliationBoundary.REPLACEMENT_BOUNDARY,
            provided_reconciliation_evidence=frozenset(),
            reconciliation_closure_proven=True,
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == ReconciliationGovernanceReason.FORBIDDEN_RECONCILIATION_MODE
    )


def test_denies_non_allowed_reconciliation_mode():
    decision = evaluate_semantic_reconciliation_governance(
        retry_governance_allowed=True,
        policy=SemanticReconciliationPolicy(
            allowed_modes=frozenset({ReconciliationMode.AUDIT_RECONCILIATION}),
            forbidden_modes=frozenset(),
            allowed_boundaries=frozenset({ReconciliationBoundary.AUDIT_BOUNDARY}),
            forbidden_boundaries=frozenset(),
            required_reconciliation_evidence=frozenset(),
            mode_boundary_rules=frozenset(),
            closure_required_modes=frozenset(),
        ),
        evidence=SemanticReconciliationEvidence(
            requested_mode=ReconciliationMode.AUTHORITATIVE_RECONCILIATION,
            requested_boundary=ReconciliationBoundary.AUDIT_BOUNDARY,
            provided_reconciliation_evidence=frozenset(),
            reconciliation_closure_proven=True,
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == ReconciliationGovernanceReason.FORBIDDEN_RECONCILIATION_MODE
    )


def test_denies_forbidden_reconciliation_boundary():
    decision = evaluate_semantic_reconciliation_governance(
        retry_governance_allowed=True,
        policy=SemanticReconciliationPolicy(
            allowed_modes=frozenset({ReconciliationMode.CLEANUP_RECONCILIATION}),
            forbidden_modes=frozenset(),
            allowed_boundaries=frozenset({ReconciliationBoundary.CLEANUP_BOUNDARY}),
            forbidden_boundaries=frozenset({ReconciliationBoundary.REPLACEMENT_BOUNDARY}),
            required_reconciliation_evidence=frozenset(),
            mode_boundary_rules=frozenset(),
            closure_required_modes=frozenset(),
        ),
        evidence=SemanticReconciliationEvidence(
            requested_mode=ReconciliationMode.CLEANUP_RECONCILIATION,
            requested_boundary=ReconciliationBoundary.REPLACEMENT_BOUNDARY,
            provided_reconciliation_evidence=frozenset(),
            reconciliation_closure_proven=True,
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == ReconciliationGovernanceReason.FORBIDDEN_RECONCILIATION_BOUNDARY
    )


def test_denies_mode_boundary_mismatch():
    rule = ReconciliationModeBoundaryRule(
        mode=ReconciliationMode.REPLACEMENT_RECONCILIATION,
        boundary=ReconciliationBoundary.REPLACEMENT_BOUNDARY,
    )

    decision = evaluate_semantic_reconciliation_governance(
        retry_governance_allowed=True,
        policy=SemanticReconciliationPolicy(
            allowed_modes=frozenset({ReconciliationMode.REPLACEMENT_RECONCILIATION}),
            forbidden_modes=frozenset(),
            allowed_boundaries=frozenset(
                {
                    ReconciliationBoundary.REPLACEMENT_BOUNDARY,
                    ReconciliationBoundary.CLEANUP_BOUNDARY,
                }
            ),
            forbidden_boundaries=frozenset(),
            required_reconciliation_evidence=frozenset(),
            mode_boundary_rules=frozenset({rule}),
            closure_required_modes=frozenset(),
        ),
        evidence=SemanticReconciliationEvidence(
            requested_mode=ReconciliationMode.REPLACEMENT_RECONCILIATION,
            requested_boundary=ReconciliationBoundary.CLEANUP_BOUNDARY,
            provided_reconciliation_evidence=frozenset(),
            reconciliation_closure_proven=True,
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == ReconciliationGovernanceReason.RECONCILIATION_MODE_BOUNDARY_MISMATCH
    )
    assert decision.mode_boundary_violations == (rule,)


def test_denies_missing_reconciliation_evidence():
    decision = evaluate_semantic_reconciliation_governance(
        retry_governance_allowed=True,
        policy=SemanticReconciliationPolicy(
            allowed_modes=frozenset({ReconciliationMode.REPLACEMENT_RECONCILIATION}),
            forbidden_modes=frozenset(),
            allowed_boundaries=frozenset({ReconciliationBoundary.REPLACEMENT_BOUNDARY}),
            forbidden_boundaries=frozenset(),
            required_reconciliation_evidence=frozenset(
                {
                    ReconciliationEvidenceRequirement.MATCHED_RECONCILIATION_PROOF,
                    ReconciliationEvidenceRequirement.REPLACEMENT_PROOF,
                }
            ),
            mode_boundary_rules=frozenset(),
            closure_required_modes=frozenset(),
        ),
        evidence=SemanticReconciliationEvidence(
            requested_mode=ReconciliationMode.REPLACEMENT_RECONCILIATION,
            requested_boundary=ReconciliationBoundary.REPLACEMENT_BOUNDARY,
            provided_reconciliation_evidence=frozenset(
                {ReconciliationEvidenceRequirement.MATCHED_RECONCILIATION_PROOF}
            ),
            reconciliation_closure_proven=True,
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == ReconciliationGovernanceReason.MISSING_RECONCILIATION_EVIDENCE
    )


def test_denies_when_reconciliation_closure_required_but_missing():
    decision = evaluate_semantic_reconciliation_governance(
        retry_governance_allowed=True,
        policy=SemanticReconciliationPolicy(
            allowed_modes=frozenset({ReconciliationMode.AUTHORITATIVE_RECONCILIATION}),
            forbidden_modes=frozenset(),
            allowed_boundaries=frozenset({ReconciliationBoundary.AUTHORITATIVE_BOUNDARY}),
            forbidden_boundaries=frozenset(),
            required_reconciliation_evidence=frozenset(),
            mode_boundary_rules=frozenset(),
            closure_required_modes=frozenset(
                {ReconciliationMode.AUTHORITATIVE_RECONCILIATION}
            ),
        ),
        evidence=SemanticReconciliationEvidence(
            requested_mode=ReconciliationMode.AUTHORITATIVE_RECONCILIATION,
            requested_boundary=ReconciliationBoundary.AUTHORITATIVE_BOUNDARY,
            provided_reconciliation_evidence=frozenset(),
            reconciliation_closure_proven=False,
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == ReconciliationGovernanceReason.RECONCILIATION_CLOSURE_REQUIRED
    )


def test_denies_when_replay_determinism_not_proven():
    decision = evaluate_semantic_reconciliation_governance(
        retry_governance_allowed=True,
        policy=SemanticReconciliationPolicy(
            allowed_modes=frozenset({ReconciliationMode.AUDIT_RECONCILIATION}),
            forbidden_modes=frozenset(),
            allowed_boundaries=frozenset({ReconciliationBoundary.AUDIT_BOUNDARY}),
            forbidden_boundaries=frozenset(),
            required_reconciliation_evidence=frozenset(),
            mode_boundary_rules=frozenset(),
            closure_required_modes=frozenset(),
            replay_required=True,
        ),
        evidence=SemanticReconciliationEvidence(
            requested_mode=ReconciliationMode.AUDIT_RECONCILIATION,
            requested_boundary=ReconciliationBoundary.AUDIT_BOUNDARY,
            provided_reconciliation_evidence=frozenset(),
            reconciliation_closure_proven=True,
            replay_determinism_proven=False,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == ReconciliationGovernanceReason.REPLAY_DETERMINISM_REQUIRED
    )


def test_denies_when_protection_continuity_not_proven():
    decision = evaluate_semantic_reconciliation_governance(
        retry_governance_allowed=True,
        policy=SemanticReconciliationPolicy(
            allowed_modes=frozenset({ReconciliationMode.EQUIVALENT_RECONCILIATION}),
            forbidden_modes=frozenset(),
            allowed_boundaries=frozenset({ReconciliationBoundary.EQUIVALENT_BOUNDARY}),
            forbidden_boundaries=frozenset(),
            required_reconciliation_evidence=frozenset(),
            mode_boundary_rules=frozenset(),
            closure_required_modes=frozenset(),
            requires_protection_continuity=True,
        ),
        evidence=SemanticReconciliationEvidence(
            requested_mode=ReconciliationMode.EQUIVALENT_RECONCILIATION,
            requested_boundary=ReconciliationBoundary.EQUIVALENT_BOUNDARY,
            provided_reconciliation_evidence=frozenset(),
            reconciliation_closure_proven=True,
            replay_determinism_proven=True,
            protection_continuity_proven=False,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == ReconciliationGovernanceReason.PROTECTION_CONTINUITY_REQUIRED
    )


def test_authorizes_reconciliation_when_governance_is_satisfied():
    rule = ReconciliationModeBoundaryRule(
        mode=ReconciliationMode.REPLACEMENT_RECONCILIATION,
        boundary=ReconciliationBoundary.REPLACEMENT_BOUNDARY,
    )

    decision = evaluate_semantic_reconciliation_governance(
        retry_governance_allowed=True,
        policy=SemanticReconciliationPolicy(
            allowed_modes=frozenset({ReconciliationMode.REPLACEMENT_RECONCILIATION}),
            forbidden_modes=frozenset(),
            allowed_boundaries=frozenset({ReconciliationBoundary.REPLACEMENT_BOUNDARY}),
            forbidden_boundaries=frozenset(),
            required_reconciliation_evidence=frozenset(
                {
                    ReconciliationEvidenceRequirement.AUTHORITATIVE_EXIT_PRESENT,
                    ReconciliationEvidenceRequirement.MATCHED_RECONCILIATION_PROOF,
                    ReconciliationEvidenceRequirement.REPLACEMENT_PROOF,
                    ReconciliationEvidenceRequirement.PROTECTION_CONTINUITY_PROVEN,
                    ReconciliationEvidenceRequirement.REPLAY_DETERMINISM_PROVEN,
                }
            ),
            mode_boundary_rules=frozenset({rule}),
            closure_required_modes=frozenset(
                {ReconciliationMode.REPLACEMENT_RECONCILIATION}
            ),
            replay_required=True,
            requires_protection_continuity=True,
        ),
        evidence=SemanticReconciliationEvidence(
            requested_mode=ReconciliationMode.REPLACEMENT_RECONCILIATION,
            requested_boundary=ReconciliationBoundary.REPLACEMENT_BOUNDARY,
            provided_reconciliation_evidence=frozenset(
                {
                    ReconciliationEvidenceRequirement.AUTHORITATIVE_EXIT_PRESENT,
                    ReconciliationEvidenceRequirement.MATCHED_RECONCILIATION_PROOF,
                    ReconciliationEvidenceRequirement.REPLACEMENT_PROOF,
                    ReconciliationEvidenceRequirement.PROTECTION_CONTINUITY_PROVEN,
                    ReconciliationEvidenceRequirement.REPLAY_DETERMINISM_PROVEN,
                }
            ),
            reconciliation_closure_proven=True,
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert isinstance(decision, SemanticReconciliationDecision)
    assert decision.allowed is True
    assert decision.reason == ReconciliationGovernanceReason.ALLOWED
    assert decision.reconciliation_mode == ReconciliationMode.REPLACEMENT_RECONCILIATION
    assert decision.reconciliation_boundary == ReconciliationBoundary.REPLACEMENT_BOUNDARY
