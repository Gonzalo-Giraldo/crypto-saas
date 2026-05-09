from app.protection.semantic_execution_planning_governance import (
    ExecutionPlanningGovernanceReason,
    ExecutionPlanningSignal,
    ExecutionPlanIntent,
    ExecutionPlanIntentScopeRule,
    ExecutionPlanOrderingRule,
    ExecutionPlanScope,
    ExecutionPlanStep,
    ExecutionPlanStepDependency,
    SemanticExecutionPlanningDecision,
    SemanticExecutionPlanningEvidence,
    SemanticExecutionPlanningPolicy,
    evaluate_semantic_execution_planning_governance,
)


def test_denies_when_orchestration_governance_not_allowed():
    decision = evaluate_semantic_execution_planning_governance(
        orchestration_governance_allowed=False,
        policy=SemanticExecutionPlanningPolicy(
            allowed_intents=frozenset({ExecutionPlanIntent.NOOP}),
            forbidden_intents=frozenset(),
            allowed_scopes=frozenset({ExecutionPlanScope.SEMANTIC_ONLY}),
            forbidden_scopes=frozenset(),
            intent_scope_rules=frozenset(),
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
            required_signals=frozenset(),
        ),
        evidence=SemanticExecutionPlanningEvidence(
            requested_intent=ExecutionPlanIntent.NOOP,
            requested_scope=ExecutionPlanScope.SEMANTIC_ONLY,
            completed_steps=frozenset(),
            requested_steps=frozenset(),
            active_signals=frozenset(),
            plan_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == ExecutionPlanningGovernanceReason.ORCHESTRATION_GOVERNANCE_NOT_ALLOWED
    )


def test_denies_forbidden_plan_intent():
    decision = evaluate_semantic_execution_planning_governance(
        orchestration_governance_allowed=True,
        policy=SemanticExecutionPlanningPolicy(
            allowed_intents=frozenset({ExecutionPlanIntent.PLAN_AUDIT_ONLY}),
            forbidden_intents=frozenset(
                {ExecutionPlanIntent.PLAN_AUTHORITATIVE_REPLACEMENT}
            ),
            allowed_scopes=frozenset({ExecutionPlanScope.REPLACEMENT_SCOPE}),
            forbidden_scopes=frozenset(),
            intent_scope_rules=frozenset(),
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
            required_signals=frozenset(),
        ),
        evidence=SemanticExecutionPlanningEvidence(
            requested_intent=ExecutionPlanIntent.PLAN_AUTHORITATIVE_REPLACEMENT,
            requested_scope=ExecutionPlanScope.REPLACEMENT_SCOPE,
            completed_steps=frozenset(),
            requested_steps=frozenset(),
            active_signals=frozenset(),
            plan_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionPlanningGovernanceReason.FORBIDDEN_PLAN_INTENT


def test_denies_forbidden_plan_scope():
    decision = evaluate_semantic_execution_planning_governance(
        orchestration_governance_allowed=True,
        policy=SemanticExecutionPlanningPolicy(
            allowed_intents=frozenset({ExecutionPlanIntent.PLAN_PROVISIONAL_CLEANUP}),
            forbidden_intents=frozenset(),
            allowed_scopes=frozenset({ExecutionPlanScope.CLEANUP_SCOPE}),
            forbidden_scopes=frozenset({ExecutionPlanScope.REPLACEMENT_SCOPE}),
            intent_scope_rules=frozenset(),
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
            required_signals=frozenset(),
        ),
        evidence=SemanticExecutionPlanningEvidence(
            requested_intent=ExecutionPlanIntent.PLAN_PROVISIONAL_CLEANUP,
            requested_scope=ExecutionPlanScope.REPLACEMENT_SCOPE,
            completed_steps=frozenset(),
            requested_steps=frozenset(),
            active_signals=frozenset(),
            plan_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionPlanningGovernanceReason.FORBIDDEN_PLAN_SCOPE
    assert decision.forbidden_scopes == (ExecutionPlanScope.REPLACEMENT_SCOPE,)


def test_denies_intent_scope_mismatch():
    rule = ExecutionPlanIntentScopeRule(
        intent=ExecutionPlanIntent.PLAN_AUTHORITATIVE_REPLACEMENT,
        scope=ExecutionPlanScope.REPLACEMENT_SCOPE,
    )

    decision = evaluate_semantic_execution_planning_governance(
        orchestration_governance_allowed=True,
        policy=SemanticExecutionPlanningPolicy(
            allowed_intents=frozenset(
                {ExecutionPlanIntent.PLAN_AUTHORITATIVE_REPLACEMENT}
            ),
            forbidden_intents=frozenset(),
            allowed_scopes=frozenset(
                {
                    ExecutionPlanScope.REPLACEMENT_SCOPE,
                    ExecutionPlanScope.CLEANUP_SCOPE,
                }
            ),
            forbidden_scopes=frozenset(),
            intent_scope_rules=frozenset({rule}),
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
            required_signals=frozenset(),
        ),
        evidence=SemanticExecutionPlanningEvidence(
            requested_intent=ExecutionPlanIntent.PLAN_AUTHORITATIVE_REPLACEMENT,
            requested_scope=ExecutionPlanScope.CLEANUP_SCOPE,
            completed_steps=frozenset(),
            requested_steps=frozenset(),
            active_signals=frozenset(),
            plan_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionPlanningGovernanceReason.INTENT_SCOPE_MISMATCH
    assert decision.intent_scope_violations == (rule,)


def test_denies_missing_required_plan_step():
    decision = evaluate_semantic_execution_planning_governance(
        orchestration_governance_allowed=True,
        policy=SemanticExecutionPlanningPolicy(
            allowed_intents=frozenset({ExecutionPlanIntent.PLAN_RECONCILIATION_ONLY}),
            forbidden_intents=frozenset(),
            allowed_scopes=frozenset({ExecutionPlanScope.RECONCILIATION_SCOPE}),
            forbidden_scopes=frozenset(),
            intent_scope_rules=frozenset(),
            required_steps=frozenset(
                {ExecutionPlanStep.PLAN_VALIDATE_RECONCILIATION}
            ),
            forbidden_steps=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
            required_signals=frozenset(),
        ),
        evidence=SemanticExecutionPlanningEvidence(
            requested_intent=ExecutionPlanIntent.PLAN_RECONCILIATION_ONLY,
            requested_scope=ExecutionPlanScope.RECONCILIATION_SCOPE,
            completed_steps=frozenset(),
            requested_steps=frozenset(),
            active_signals=frozenset(),
            plan_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == ExecutionPlanningGovernanceReason.MISSING_REQUIRED_PLAN_STEP
    )


def test_denies_forbidden_plan_step_present():
    decision = evaluate_semantic_execution_planning_governance(
        orchestration_governance_allowed=True,
        policy=SemanticExecutionPlanningPolicy(
            allowed_intents=frozenset({ExecutionPlanIntent.PLAN_AUDIT_ONLY}),
            forbidden_intents=frozenset(),
            allowed_scopes=frozenset({ExecutionPlanScope.AUDIT_SCOPE}),
            forbidden_scopes=frozenset(),
            intent_scope_rules=frozenset(),
            required_steps=frozenset(),
            forbidden_steps=frozenset({ExecutionPlanStep.PLAN_VALIDATE_FINALITY}),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
            required_signals=frozenset(),
        ),
        evidence=SemanticExecutionPlanningEvidence(
            requested_intent=ExecutionPlanIntent.PLAN_AUDIT_ONLY,
            requested_scope=ExecutionPlanScope.AUDIT_SCOPE,
            completed_steps=frozenset({ExecutionPlanStep.PLAN_VALIDATE_FINALITY}),
            requested_steps=frozenset(),
            active_signals=frozenset(),
            plan_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == ExecutionPlanningGovernanceReason.FORBIDDEN_PLAN_STEP_PRESENT
    )


def test_denies_plan_step_ordering_violation():
    rule = ExecutionPlanOrderingRule(
        before=ExecutionPlanStep.PLAN_VALIDATE_ORCHESTRATION,
        after=ExecutionPlanStep.PLAN_RECORD_AUDIT,
    )

    decision = evaluate_semantic_execution_planning_governance(
        orchestration_governance_allowed=True,
        policy=SemanticExecutionPlanningPolicy(
            allowed_intents=frozenset({ExecutionPlanIntent.PLAN_AUDIT_ONLY}),
            forbidden_intents=frozenset(),
            allowed_scopes=frozenset({ExecutionPlanScope.AUDIT_SCOPE}),
            forbidden_scopes=frozenset(),
            intent_scope_rules=frozenset(),
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            ordering_rules=frozenset({rule}),
            step_dependencies=frozenset(),
            required_signals=frozenset(),
        ),
        evidence=SemanticExecutionPlanningEvidence(
            requested_intent=ExecutionPlanIntent.PLAN_AUDIT_ONLY,
            requested_scope=ExecutionPlanScope.AUDIT_SCOPE,
            completed_steps=frozenset(),
            requested_steps=frozenset({ExecutionPlanStep.PLAN_RECORD_AUDIT}),
            active_signals=frozenset(),
            plan_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == ExecutionPlanningGovernanceReason.PLAN_STEP_ORDERING_VIOLATION
    )
    assert decision.ordering_violations == (rule,)


def test_denies_plan_step_dependency_violation():
    dependency = ExecutionPlanStepDependency(
        required_step=ExecutionPlanStep.PLAN_VALIDATE_RETRY,
        dependent_step=ExecutionPlanStep.PLAN_VALIDATE_RECONCILIATION,
    )

    decision = evaluate_semantic_execution_planning_governance(
        orchestration_governance_allowed=True,
        policy=SemanticExecutionPlanningPolicy(
            allowed_intents=frozenset({ExecutionPlanIntent.PLAN_RECONCILIATION_ONLY}),
            forbidden_intents=frozenset(),
            allowed_scopes=frozenset({ExecutionPlanScope.RECONCILIATION_SCOPE}),
            forbidden_scopes=frozenset(),
            intent_scope_rules=frozenset(),
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset({dependency}),
            required_signals=frozenset(),
        ),
        evidence=SemanticExecutionPlanningEvidence(
            requested_intent=ExecutionPlanIntent.PLAN_RECONCILIATION_ONLY,
            requested_scope=ExecutionPlanScope.RECONCILIATION_SCOPE,
            completed_steps=frozenset(),
            requested_steps=frozenset(
                {ExecutionPlanStep.PLAN_VALIDATE_RECONCILIATION}
            ),
            active_signals=frozenset(),
            plan_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == ExecutionPlanningGovernanceReason.PLAN_STEP_DEPENDENCY_VIOLATION
    )
    assert decision.dependency_violations == (dependency,)


def test_denies_missing_required_signal():
    decision = evaluate_semantic_execution_planning_governance(
        orchestration_governance_allowed=True,
        policy=SemanticExecutionPlanningPolicy(
            allowed_intents=frozenset({ExecutionPlanIntent.PLAN_AUDIT_ONLY}),
            forbidden_intents=frozenset(),
            allowed_scopes=frozenset({ExecutionPlanScope.AUDIT_SCOPE}),
            forbidden_scopes=frozenset(),
            intent_scope_rules=frozenset(),
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
            required_signals=frozenset({ExecutionPlanningSignal.PLAN_CLOSURE_PROVEN}),
        ),
        evidence=SemanticExecutionPlanningEvidence(
            requested_intent=ExecutionPlanIntent.PLAN_AUDIT_ONLY,
            requested_scope=ExecutionPlanScope.AUDIT_SCOPE,
            completed_steps=frozenset(),
            requested_steps=frozenset(),
            active_signals=frozenset(),
            plan_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionPlanningGovernanceReason.MISSING_REQUIRED_SIGNAL


def test_denies_when_plan_closure_not_proven():
    decision = evaluate_semantic_execution_planning_governance(
        orchestration_governance_allowed=True,
        policy=SemanticExecutionPlanningPolicy(
            allowed_intents=frozenset({ExecutionPlanIntent.PLAN_AUDIT_ONLY}),
            forbidden_intents=frozenset(),
            allowed_scopes=frozenset({ExecutionPlanScope.AUDIT_SCOPE}),
            forbidden_scopes=frozenset(),
            intent_scope_rules=frozenset(),
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
            required_signals=frozenset(),
            plan_closure_required=True,
        ),
        evidence=SemanticExecutionPlanningEvidence(
            requested_intent=ExecutionPlanIntent.PLAN_AUDIT_ONLY,
            requested_scope=ExecutionPlanScope.AUDIT_SCOPE,
            completed_steps=frozenset(),
            requested_steps=frozenset(),
            active_signals=frozenset(),
            plan_closure_proven=False,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionPlanningGovernanceReason.PLAN_CLOSURE_REQUIRED


def test_denies_when_protection_continuity_not_proven():
    decision = evaluate_semantic_execution_planning_governance(
        orchestration_governance_allowed=True,
        policy=SemanticExecutionPlanningPolicy(
            allowed_intents=frozenset({ExecutionPlanIntent.PLAN_AUTHORITATIVE_CREATION}),
            forbidden_intents=frozenset(),
            allowed_scopes=frozenset({ExecutionPlanScope.AUTHORITATIVE_SCOPE}),
            forbidden_scopes=frozenset(),
            intent_scope_rules=frozenset(),
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
            required_signals=frozenset(),
            requires_protection_continuity=True,
        ),
        evidence=SemanticExecutionPlanningEvidence(
            requested_intent=ExecutionPlanIntent.PLAN_AUTHORITATIVE_CREATION,
            requested_scope=ExecutionPlanScope.AUTHORITATIVE_SCOPE,
            completed_steps=frozenset(),
            requested_steps=frozenset(),
            active_signals=frozenset(),
            plan_closure_proven=True,
            protection_continuity_proven=False,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == ExecutionPlanningGovernanceReason.PROTECTION_CONTINUITY_REQUIRED
    )


def test_denies_when_replay_determinism_not_proven():
    decision = evaluate_semantic_execution_planning_governance(
        orchestration_governance_allowed=True,
        policy=SemanticExecutionPlanningPolicy(
            allowed_intents=frozenset({ExecutionPlanIntent.PLAN_RECONCILIATION_ONLY}),
            forbidden_intents=frozenset(),
            allowed_scopes=frozenset({ExecutionPlanScope.RECONCILIATION_SCOPE}),
            forbidden_scopes=frozenset(),
            intent_scope_rules=frozenset(),
            required_steps=frozenset(),
            forbidden_steps=frozenset(),
            ordering_rules=frozenset(),
            step_dependencies=frozenset(),
            required_signals=frozenset(),
            requires_replay_determinism=True,
        ),
        evidence=SemanticExecutionPlanningEvidence(
            requested_intent=ExecutionPlanIntent.PLAN_RECONCILIATION_ONLY,
            requested_scope=ExecutionPlanScope.RECONCILIATION_SCOPE,
            completed_steps=frozenset(),
            requested_steps=frozenset(),
            active_signals=frozenset(),
            plan_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=False,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == ExecutionPlanningGovernanceReason.REPLAY_DETERMINISM_REQUIRED
    )


def test_authorizes_execution_planning_when_governance_is_satisfied():
    intent_scope_rule = ExecutionPlanIntentScopeRule(
        intent=ExecutionPlanIntent.PLAN_AUTHORITATIVE_REPLACEMENT,
        scope=ExecutionPlanScope.REPLACEMENT_SCOPE,
    )
    audit_ordering = ExecutionPlanOrderingRule(
        before=ExecutionPlanStep.PLAN_VALIDATE_ORCHESTRATION,
        after=ExecutionPlanStep.PLAN_RECORD_AUDIT,
    )
    reconciliation_dependency = ExecutionPlanStepDependency(
        required_step=ExecutionPlanStep.PLAN_VALIDATE_RECONCILIATION,
        dependent_step=ExecutionPlanStep.PLAN_VALIDATE_ORCHESTRATION,
    )

    decision = evaluate_semantic_execution_planning_governance(
        orchestration_governance_allowed=True,
        policy=SemanticExecutionPlanningPolicy(
            allowed_intents=frozenset(
                {ExecutionPlanIntent.PLAN_AUTHORITATIVE_REPLACEMENT}
            ),
            forbidden_intents=frozenset(),
            allowed_scopes=frozenset({ExecutionPlanScope.REPLACEMENT_SCOPE}),
            forbidden_scopes=frozenset(),
            intent_scope_rules=frozenset({intent_scope_rule}),
            required_steps=frozenset(
                {
                    ExecutionPlanStep.PLAN_VALIDATE_RECONCILIATION,
                    ExecutionPlanStep.PLAN_VALIDATE_ORCHESTRATION,
                    ExecutionPlanStep.PLAN_RECORD_AUDIT,
                }
            ),
            forbidden_steps=frozenset(),
            ordering_rules=frozenset({audit_ordering}),
            step_dependencies=frozenset({reconciliation_dependency}),
            required_signals=frozenset(
                {
                    ExecutionPlanningSignal.PLAN_TOPOLOGY_PROVEN,
                    ExecutionPlanningSignal.PLAN_SCOPE_PROVEN,
                    ExecutionPlanningSignal.PLAN_SEQUENCE_PROVEN,
                    ExecutionPlanningSignal.PLAN_CLOSURE_PROVEN,
                    ExecutionPlanningSignal.PROTECTION_CONTINUITY_PROVEN,
                    ExecutionPlanningSignal.REPLAY_DETERMINISM_PROVEN,
                }
            ),
            plan_closure_required=True,
            requires_protection_continuity=True,
            requires_replay_determinism=True,
        ),
        evidence=SemanticExecutionPlanningEvidence(
            requested_intent=ExecutionPlanIntent.PLAN_AUTHORITATIVE_REPLACEMENT,
            requested_scope=ExecutionPlanScope.REPLACEMENT_SCOPE,
            completed_steps=frozenset(
                {
                    ExecutionPlanStep.PLAN_VALIDATE_RECONCILIATION,
                    ExecutionPlanStep.PLAN_VALIDATE_ORCHESTRATION,
                }
            ),
            requested_steps=frozenset({ExecutionPlanStep.PLAN_RECORD_AUDIT}),
            active_signals=frozenset(
                {
                    ExecutionPlanningSignal.PLAN_TOPOLOGY_PROVEN,
                    ExecutionPlanningSignal.PLAN_SCOPE_PROVEN,
                    ExecutionPlanningSignal.PLAN_SEQUENCE_PROVEN,
                    ExecutionPlanningSignal.PLAN_CLOSURE_PROVEN,
                    ExecutionPlanningSignal.PROTECTION_CONTINUITY_PROVEN,
                    ExecutionPlanningSignal.REPLAY_DETERMINISM_PROVEN,
                }
            ),
            plan_closure_proven=True,
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert isinstance(decision, SemanticExecutionPlanningDecision)
    assert decision.allowed is True
    assert decision.reason == ExecutionPlanningGovernanceReason.ALLOWED
    assert decision.plan_intent == ExecutionPlanIntent.PLAN_AUTHORITATIVE_REPLACEMENT
    assert decision.plan_scope == ExecutionPlanScope.REPLACEMENT_SCOPE
