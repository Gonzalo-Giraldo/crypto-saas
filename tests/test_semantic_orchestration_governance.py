from app.protection.semantic_orchestration_governance import (
    OrchestrationBoundary,
    OrchestrationGovernanceReason,
    OrchestrationOrderingRule,
    OrchestrationSignal,
    OrchestrationStep,
    OrchestrationStepDependency,
    SemanticOrchestrationDecision,
    SemanticOrchestrationEvidence,
    SemanticOrchestrationPolicy,
    evaluate_semantic_orchestration_governance,
)


def test_denies_when_consistency_governance_not_allowed():
    decision = evaluate_semantic_orchestration_governance(
        consistency_governance_allowed=False,
        policy=SemanticOrchestrationPolicy(
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            allowed_boundaries=frozenset({OrchestrationBoundary.SEMANTIC_ONLY}),
            forbidden_boundaries=frozenset(),
            required_signals=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
        ),
        evidence=SemanticOrchestrationEvidence(
            completed_steps=frozenset(),
            requested_steps=frozenset(),
            requested_boundary=OrchestrationBoundary.SEMANTIC_ONLY,
            active_signals=frozenset(),
            orchestration_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        OrchestrationGovernanceReason.CONSISTENCY_GOVERNANCE_NOT_ALLOWED
    )


def test_denies_missing_required_step():
    decision = evaluate_semantic_orchestration_governance(
        consistency_governance_allowed=True,
        policy=SemanticOrchestrationPolicy(
            required_steps=frozenset({OrchestrationStep.VALIDATE_CONSISTENCY}),
            forbidden_steps=frozenset(),
            allowed_boundaries=frozenset({OrchestrationBoundary.SEMANTIC_ONLY}),
            forbidden_boundaries=frozenset(),
            required_signals=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
        ),
        evidence=SemanticOrchestrationEvidence(
            completed_steps=frozenset({OrchestrationStep.VALIDATE_RECONCILIATION}),
            requested_steps=frozenset(),
            requested_boundary=OrchestrationBoundary.SEMANTIC_ONLY,
            active_signals=frozenset(),
            orchestration_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == OrchestrationGovernanceReason.MISSING_REQUIRED_STEP
    assert decision.missing_steps == (OrchestrationStep.VALIDATE_CONSISTENCY,)


def test_denies_forbidden_step_present():
    decision = evaluate_semantic_orchestration_governance(
        consistency_governance_allowed=True,
        policy=SemanticOrchestrationPolicy(
            required_steps=frozenset(),
            forbidden_steps=frozenset({OrchestrationStep.RECORD_AUDIT_TRACE}),
            allowed_boundaries=frozenset({OrchestrationBoundary.SEMANTIC_ONLY}),
            forbidden_boundaries=frozenset(),
            required_signals=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
        ),
        evidence=SemanticOrchestrationEvidence(
            completed_steps=frozenset({OrchestrationStep.RECORD_AUDIT_TRACE}),
            requested_steps=frozenset(),
            requested_boundary=OrchestrationBoundary.SEMANTIC_ONLY,
            active_signals=frozenset(),
            orchestration_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == OrchestrationGovernanceReason.FORBIDDEN_STEP_PRESENT


def test_denies_forbidden_boundary():
    decision = evaluate_semantic_orchestration_governance(
        consistency_governance_allowed=True,
        policy=SemanticOrchestrationPolicy(
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            allowed_boundaries=frozenset({OrchestrationBoundary.SEMANTIC_ONLY}),
            forbidden_boundaries=frozenset({OrchestrationBoundary.PRE_EXECUTION}),
            required_signals=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
        ),
        evidence=SemanticOrchestrationEvidence(
            completed_steps=frozenset(),
            requested_steps=frozenset(),
            requested_boundary=OrchestrationBoundary.PRE_EXECUTION,
            active_signals=frozenset(),
            orchestration_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == OrchestrationGovernanceReason.FORBIDDEN_BOUNDARY
    assert decision.forbidden_boundaries == (OrchestrationBoundary.PRE_EXECUTION,)


def test_denies_missing_required_signal():
    decision = evaluate_semantic_orchestration_governance(
        consistency_governance_allowed=True,
        policy=SemanticOrchestrationPolicy(
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            allowed_boundaries=frozenset({OrchestrationBoundary.SEMANTIC_ONLY}),
            forbidden_boundaries=frozenset(),
            required_signals=frozenset({OrchestrationSignal.ORDERING_PROVEN}),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
        ),
        evidence=SemanticOrchestrationEvidence(
            completed_steps=frozenset(),
            requested_steps=frozenset(),
            requested_boundary=OrchestrationBoundary.SEMANTIC_ONLY,
            active_signals=frozenset(),
            orchestration_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == OrchestrationGovernanceReason.MISSING_REQUIRED_SIGNAL
    assert decision.missing_signals == (OrchestrationSignal.ORDERING_PROVEN,)


def test_denies_step_ordering_violation():
    rule = OrchestrationOrderingRule(
        before=OrchestrationStep.VALIDATE_CONSISTENCY,
        after=OrchestrationStep.RECORD_AUDIT_TRACE,
    )

    decision = evaluate_semantic_orchestration_governance(
        consistency_governance_allowed=True,
        policy=SemanticOrchestrationPolicy(
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            allowed_boundaries=frozenset({OrchestrationBoundary.SEMANTIC_ONLY}),
            forbidden_boundaries=frozenset(),
            required_signals=frozenset(),
            ordering_rules=frozenset({rule}),
            step_dependencies=frozenset(),
        ),
        evidence=SemanticOrchestrationEvidence(
            completed_steps=frozenset(),
            requested_steps=frozenset({OrchestrationStep.RECORD_AUDIT_TRACE}),
            requested_boundary=OrchestrationBoundary.SEMANTIC_ONLY,
            active_signals=frozenset(),
            orchestration_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == OrchestrationGovernanceReason.STEP_ORDERING_VIOLATION
    assert decision.ordering_violations == (rule,)


def test_denies_step_dependency_violation():
    dependency = OrchestrationStepDependency(
        required_step=OrchestrationStep.VALIDATE_RETRY,
        dependent_step=OrchestrationStep.VALIDATE_RECONCILIATION,
    )

    decision = evaluate_semantic_orchestration_governance(
        consistency_governance_allowed=True,
        policy=SemanticOrchestrationPolicy(
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            allowed_boundaries=frozenset({OrchestrationBoundary.SEMANTIC_ONLY}),
            forbidden_boundaries=frozenset(),
            required_signals=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset({dependency}),
        ),
        evidence=SemanticOrchestrationEvidence(
            completed_steps=frozenset(),
            requested_steps=frozenset({OrchestrationStep.VALIDATE_RECONCILIATION}),
            requested_boundary=OrchestrationBoundary.SEMANTIC_ONLY,
            active_signals=frozenset(),
            orchestration_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == OrchestrationGovernanceReason.STEP_DEPENDENCY_VIOLATION
    assert decision.dependency_violations == (dependency,)


def test_denies_when_orchestration_closure_not_proven():
    decision = evaluate_semantic_orchestration_governance(
        consistency_governance_allowed=True,
        policy=SemanticOrchestrationPolicy(
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            allowed_boundaries=frozenset({OrchestrationBoundary.SEMANTIC_ONLY}),
            forbidden_boundaries=frozenset(),
            required_signals=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
            closure_required=True,
        ),
        evidence=SemanticOrchestrationEvidence(
            completed_steps=frozenset(),
            requested_steps=frozenset(),
            requested_boundary=OrchestrationBoundary.SEMANTIC_ONLY,
            active_signals=frozenset(),
            orchestration_closure_proven=False,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        OrchestrationGovernanceReason.ORCHESTRATION_CLOSURE_REQUIRED
    )


def test_denies_when_protection_continuity_not_proven():
    decision = evaluate_semantic_orchestration_governance(
        consistency_governance_allowed=True,
        policy=SemanticOrchestrationPolicy(
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            allowed_boundaries=frozenset({OrchestrationBoundary.SEMANTIC_ONLY}),
            forbidden_boundaries=frozenset(),
            required_signals=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
            requires_protection_continuity=True,
        ),
        evidence=SemanticOrchestrationEvidence(
            completed_steps=frozenset(),
            requested_steps=frozenset(),
            requested_boundary=OrchestrationBoundary.SEMANTIC_ONLY,
            active_signals=frozenset(),
            orchestration_closure_proven=True,
            protection_continuity_proven=False,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == OrchestrationGovernanceReason.PROTECTION_CONTINUITY_REQUIRED


def test_denies_when_replay_determinism_not_proven():
    decision = evaluate_semantic_orchestration_governance(
        consistency_governance_allowed=True,
        policy=SemanticOrchestrationPolicy(
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            allowed_boundaries=frozenset({OrchestrationBoundary.SEMANTIC_ONLY}),
            forbidden_boundaries=frozenset(),
            required_signals=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
            requires_replay_determinism=True,
        ),
        evidence=SemanticOrchestrationEvidence(
            completed_steps=frozenset(),
            requested_steps=frozenset(),
            requested_boundary=OrchestrationBoundary.SEMANTIC_ONLY,
            active_signals=frozenset(),
            orchestration_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=False,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == OrchestrationGovernanceReason.REPLAY_DETERMINISM_REQUIRED


def test_authorizes_orchestration_when_governance_is_satisfied():
    retry_dependency = OrchestrationStepDependency(
        required_step=OrchestrationStep.VALIDATE_RETRY,
        dependent_step=OrchestrationStep.VALIDATE_RECONCILIATION,
    )
    reconciliation_dependency = OrchestrationStepDependency(
        required_step=OrchestrationStep.VALIDATE_RECONCILIATION,
        dependent_step=OrchestrationStep.VALIDATE_CONSISTENCY,
    )
    audit_ordering = OrchestrationOrderingRule(
        before=OrchestrationStep.VALIDATE_CONSISTENCY,
        after=OrchestrationStep.RECORD_AUDIT_TRACE,
    )

    decision = evaluate_semantic_orchestration_governance(
        consistency_governance_allowed=True,
        policy=SemanticOrchestrationPolicy(
            required_steps=frozenset(
                {
                    OrchestrationStep.VALIDATE_RETRY,
                    OrchestrationStep.VALIDATE_RECONCILIATION,
                    OrchestrationStep.VALIDATE_CONSISTENCY,
                    OrchestrationStep.RECORD_AUDIT_TRACE,
                }
            ),
            forbidden_steps=frozenset(),
            allowed_boundaries=frozenset({OrchestrationBoundary.SEMANTIC_ONLY}),
            forbidden_boundaries=frozenset(),
            required_signals=frozenset(
                {
                    OrchestrationSignal.ORDERING_PROVEN,
                    OrchestrationSignal.DEPENDENCIES_PROVEN,
                    OrchestrationSignal.CONSISTENCY_PROVEN,
                    OrchestrationSignal.REPLAY_DETERMINISM_PROVEN,
                    OrchestrationSignal.PROTECTION_CONTINUITY_PROVEN,
                    OrchestrationSignal.AUDIT_TRACE_READY,
                }
            ),
            ordering_rules=frozenset({audit_ordering}),
            step_dependencies=frozenset(
                {
                    retry_dependency,
                    reconciliation_dependency,
                }
            ),
            closure_required=True,
            requires_protection_continuity=True,
            requires_replay_determinism=True,
        ),
        evidence=SemanticOrchestrationEvidence(
            completed_steps=frozenset(
                {
                    OrchestrationStep.VALIDATE_RETRY,
                    OrchestrationStep.VALIDATE_RECONCILIATION,
                    OrchestrationStep.VALIDATE_CONSISTENCY,
                }
            ),
            requested_steps=frozenset({OrchestrationStep.RECORD_AUDIT_TRACE}),
            requested_boundary=OrchestrationBoundary.SEMANTIC_ONLY,
            active_signals=frozenset(
                {
                    OrchestrationSignal.ORDERING_PROVEN,
                    OrchestrationSignal.DEPENDENCIES_PROVEN,
                    OrchestrationSignal.CONSISTENCY_PROVEN,
                    OrchestrationSignal.REPLAY_DETERMINISM_PROVEN,
                    OrchestrationSignal.PROTECTION_CONTINUITY_PROVEN,
                    OrchestrationSignal.AUDIT_TRACE_READY,
                }
            ),
            orchestration_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert isinstance(decision, SemanticOrchestrationDecision)
    assert decision.allowed is True
    assert decision.reason == OrchestrationGovernanceReason.ALLOWED
