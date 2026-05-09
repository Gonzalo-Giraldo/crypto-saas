from app.protection.semantic_consistency_governance import (
    ConsistencyContradiction,
    ConsistencyGovernanceReason,
    ConsistencyLayer,
    ConsistencyLayerDependency,
    ConsistencySignal,
    SemanticConsistencyDecision,
    SemanticConsistencyEvidence,
    SemanticConsistencyPolicy,
    evaluate_semantic_consistency_governance,
)


def test_denies_when_reconciliation_governance_not_allowed():
    decision = evaluate_semantic_consistency_governance(
        reconciliation_governance_allowed=False,
        policy=SemanticConsistencyPolicy(
            required_layers=frozenset(),
            forbidden_layers=frozenset(),
            required_signals=frozenset(),
            forbidden_signals=frozenset(),
            forbidden_contradictions=frozenset(),
            layer_dependencies=frozenset(),
        ),
        evidence=SemanticConsistencyEvidence(
            active_layers=frozenset(),
            active_signals=frozenset(),
            observed_contradictions=frozenset(),
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        ConsistencyGovernanceReason.RECONCILIATION_GOVERNANCE_NOT_ALLOWED
    )


def test_denies_missing_required_layer():
    decision = evaluate_semantic_consistency_governance(
        reconciliation_governance_allowed=True,
        policy=SemanticConsistencyPolicy(
            required_layers=frozenset({ConsistencyLayer.RECONCILIATION}),
            forbidden_layers=frozenset(),
            required_signals=frozenset(),
            forbidden_signals=frozenset(),
            forbidden_contradictions=frozenset(),
            layer_dependencies=frozenset(),
        ),
        evidence=SemanticConsistencyEvidence(
            active_layers=frozenset({ConsistencyLayer.RETRY}),
            active_signals=frozenset(),
            observed_contradictions=frozenset(),
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ConsistencyGovernanceReason.MISSING_REQUIRED_LAYER
    assert decision.missing_layers == (ConsistencyLayer.RECONCILIATION,)


def test_denies_missing_required_signal():
    decision = evaluate_semantic_consistency_governance(
        reconciliation_governance_allowed=True,
        policy=SemanticConsistencyPolicy(
            required_layers=frozenset(),
            forbidden_layers=frozenset(),
            required_signals=frozenset(
                {ConsistencySignal.RECONCILIATION_CLOSED}
            ),
            forbidden_signals=frozenset(),
            forbidden_contradictions=frozenset(),
            layer_dependencies=frozenset(),
        ),
        evidence=SemanticConsistencyEvidence(
            active_layers=frozenset({ConsistencyLayer.RECONCILIATION}),
            active_signals=frozenset(),
            observed_contradictions=frozenset(),
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ConsistencyGovernanceReason.MISSING_REQUIRED_SIGNAL


def test_denies_forbidden_layer_present():
    decision = evaluate_semantic_consistency_governance(
        reconciliation_governance_allowed=True,
        policy=SemanticConsistencyPolicy(
            required_layers=frozenset(),
            forbidden_layers=frozenset({ConsistencyLayer.RETRY}),
            required_signals=frozenset(),
            forbidden_signals=frozenset(),
            forbidden_contradictions=frozenset(),
            layer_dependencies=frozenset(),
        ),
        evidence=SemanticConsistencyEvidence(
            active_layers=frozenset({ConsistencyLayer.RETRY}),
            active_signals=frozenset(),
            observed_contradictions=frozenset(),
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ConsistencyGovernanceReason.FORBIDDEN_LAYER_PRESENT
    assert decision.forbidden_layers == (ConsistencyLayer.RETRY,)


def test_denies_forbidden_signal_present():
    decision = evaluate_semantic_consistency_governance(
        reconciliation_governance_allowed=True,
        policy=SemanticConsistencyPolicy(
            required_layers=frozenset(),
            forbidden_layers=frozenset(),
            required_signals=frozenset(),
            forbidden_signals=frozenset({ConsistencySignal.RETRY_ADMISSIBLE}),
            forbidden_contradictions=frozenset(),
            layer_dependencies=frozenset(),
        ),
        evidence=SemanticConsistencyEvidence(
            active_layers=frozenset({ConsistencyLayer.FINALITY}),
            active_signals=frozenset({ConsistencySignal.RETRY_ADMISSIBLE}),
            observed_contradictions=frozenset(),
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ConsistencyGovernanceReason.FORBIDDEN_SIGNAL_PRESENT


def test_denies_semantic_contradiction():
    decision = evaluate_semantic_consistency_governance(
        reconciliation_governance_allowed=True,
        policy=SemanticConsistencyPolicy(
            required_layers=frozenset(),
            forbidden_layers=frozenset(),
            required_signals=frozenset(),
            forbidden_signals=frozenset(),
            forbidden_contradictions=frozenset(
                {ConsistencyContradiction.RETRY_AFTER_FINALITY}
            ),
            layer_dependencies=frozenset(),
        ),
        evidence=SemanticConsistencyEvidence(
            active_layers=frozenset(
                {
                    ConsistencyLayer.FINALITY,
                    ConsistencyLayer.RETRY,
                }
            ),
            active_signals=frozenset(),
            observed_contradictions=frozenset(
                {ConsistencyContradiction.RETRY_AFTER_FINALITY}
            ),
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ConsistencyGovernanceReason.SEMANTIC_CONTRADICTION


def test_denies_layer_dependency_violation():
    dependency = ConsistencyLayerDependency(
        required_layer=ConsistencyLayer.RETRY,
        dependent_layer=ConsistencyLayer.RECONCILIATION,
    )

    decision = evaluate_semantic_consistency_governance(
        reconciliation_governance_allowed=True,
        policy=SemanticConsistencyPolicy(
            required_layers=frozenset(),
            forbidden_layers=frozenset(),
            required_signals=frozenset(),
            forbidden_signals=frozenset(),
            forbidden_contradictions=frozenset(),
            layer_dependencies=frozenset({dependency}),
        ),
        evidence=SemanticConsistencyEvidence(
            active_layers=frozenset({ConsistencyLayer.RECONCILIATION}),
            active_signals=frozenset(),
            observed_contradictions=frozenset(),
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ConsistencyGovernanceReason.LAYER_DEPENDENCY_VIOLATION
    assert decision.layer_dependency_violations == (dependency,)


def test_denies_when_protection_continuity_not_proven():
    decision = evaluate_semantic_consistency_governance(
        reconciliation_governance_allowed=True,
        policy=SemanticConsistencyPolicy(
            required_layers=frozenset(),
            forbidden_layers=frozenset(),
            required_signals=frozenset(),
            forbidden_signals=frozenset(),
            forbidden_contradictions=frozenset(),
            layer_dependencies=frozenset(),
            requires_protection_continuity=True,
        ),
        evidence=SemanticConsistencyEvidence(
            active_layers=frozenset({ConsistencyLayer.RECONCILIATION}),
            active_signals=frozenset(),
            observed_contradictions=frozenset(),
            protection_continuity_proven=False,
            replay_determinism_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ConsistencyGovernanceReason.PROTECTION_CONTINUITY_REQUIRED


def test_denies_when_replay_determinism_not_proven():
    decision = evaluate_semantic_consistency_governance(
        reconciliation_governance_allowed=True,
        policy=SemanticConsistencyPolicy(
            required_layers=frozenset(),
            forbidden_layers=frozenset(),
            required_signals=frozenset(),
            forbidden_signals=frozenset(),
            forbidden_contradictions=frozenset(),
            layer_dependencies=frozenset(),
            requires_replay_determinism=True,
        ),
        evidence=SemanticConsistencyEvidence(
            active_layers=frozenset({ConsistencyLayer.RECONCILIATION}),
            active_signals=frozenset(),
            observed_contradictions=frozenset(),
            protection_continuity_proven=True,
            replay_determinism_proven=False,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ConsistencyGovernanceReason.REPLAY_DETERMINISM_REQUIRED


def test_authorizes_consistency_when_governance_is_satisfied():
    retry_dependency = ConsistencyLayerDependency(
        required_layer=ConsistencyLayer.RETRY,
        dependent_layer=ConsistencyLayer.RECONCILIATION,
    )
    recovery_dependency = ConsistencyLayerDependency(
        required_layer=ConsistencyLayer.RECOVERY,
        dependent_layer=ConsistencyLayer.RETRY,
    )

    decision = evaluate_semantic_consistency_governance(
        reconciliation_governance_allowed=True,
        policy=SemanticConsistencyPolicy(
            required_layers=frozenset(
                {
                    ConsistencyLayer.RECOVERY,
                    ConsistencyLayer.RETRY,
                    ConsistencyLayer.RECONCILIATION,
                    ConsistencyLayer.FINALITY,
                }
            ),
            forbidden_layers=frozenset(),
            required_signals=frozenset(
                {
                    ConsistencySignal.PROTECTION_CONTINUITY_PROVEN,
                    ConsistencySignal.REPLAY_DETERMINISM_PROVEN,
                    ConsistencySignal.RECONCILIATION_CLOSED,
                    ConsistencySignal.FINALITY_CONFIRMED,
                }
            ),
            forbidden_signals=frozenset(),
            forbidden_contradictions=frozenset(
                {
                    ConsistencyContradiction.RETRY_AFTER_FINALITY,
                    ConsistencyContradiction.RECONCILIATION_WITHOUT_CLOSURE,
                    ConsistencyContradiction.RECOVERY_WITHOUT_REPLAY_DETERMINISM,
                }
            ),
            layer_dependencies=frozenset(
                {
                    retry_dependency,
                    recovery_dependency,
                }
            ),
            requires_protection_continuity=True,
            requires_replay_determinism=True,
        ),
        evidence=SemanticConsistencyEvidence(
            active_layers=frozenset(
                {
                    ConsistencyLayer.RECOVERY,
                    ConsistencyLayer.RETRY,
                    ConsistencyLayer.RECONCILIATION,
                    ConsistencyLayer.FINALITY,
                }
            ),
            active_signals=frozenset(
                {
                    ConsistencySignal.PROTECTION_CONTINUITY_PROVEN,
                    ConsistencySignal.REPLAY_DETERMINISM_PROVEN,
                    ConsistencySignal.RECONCILIATION_CLOSED,
                    ConsistencySignal.FINALITY_CONFIRMED,
                }
            ),
            observed_contradictions=frozenset(),
            protection_continuity_proven=True,
            replay_determinism_proven=True,
        ),
    )

    assert isinstance(decision, SemanticConsistencyDecision)
    assert decision.allowed is True
    assert decision.reason == ConsistencyGovernanceReason.ALLOWED
