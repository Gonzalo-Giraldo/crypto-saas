from app.protection.execution_state_convergence_semantics import (
    ConvergenceDependencyRule,
    ConvergenceReason,
    ConvergenceState,
    ExecutionStateConvergenceDecision,
    ExecutionStateConvergenceEvidence,
    ExecutionStateConvergencePolicy,
    evaluate_execution_state_convergence_semantics,
)


def test_denies_when_topology_semantics_not_allowed():
    decision = evaluate_execution_state_convergence_semantics(
        topology_semantics_allowed=False,
        policy=ExecutionStateConvergencePolicy(
            required_states=frozenset(),
            forbidden_states=frozenset(),
            unresolved_states=frozenset(),
            dependency_rules=frozenset(),
            authoritative_states=frozenset(),
            stable_baseline_states=frozenset(),
        ),
        evidence=ExecutionStateConvergenceEvidence(
            active_states=frozenset(),
            requested_states=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        ConvergenceReason.TOPOLOGY_SEMANTICS_NOT_ALLOWED
    )


def test_denies_missing_required_state():
    decision = evaluate_execution_state_convergence_semantics(
        topology_semantics_allowed=True,
        policy=ExecutionStateConvergencePolicy(
            required_states=frozenset(
                {ConvergenceState.PROVISIONAL_PRESENT}
            ),
            forbidden_states=frozenset(),
            unresolved_states=frozenset(),
            dependency_rules=frozenset(),
            authoritative_states=frozenset(),
            stable_baseline_states=frozenset(),
        ),
        evidence=ExecutionStateConvergenceEvidence(
            active_states=frozenset(),
            requested_states=frozenset(
                {ConvergenceState.AUTHORITATIVE_CREATED}
            ),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        ConvergenceReason.MISSING_REQUIRED_CONVERGENCE_STATE
    )


def test_denies_forbidden_state():
    decision = evaluate_execution_state_convergence_semantics(
        topology_semantics_allowed=True,
        policy=ExecutionStateConvergencePolicy(
            required_states=frozenset(),
            forbidden_states=frozenset(
                {ConvergenceState.TRAILING_ACTIVE}
            ),
            unresolved_states=frozenset(),
            dependency_rules=frozenset(),
            authoritative_states=frozenset(),
            stable_baseline_states=frozenset(),
        ),
        evidence=ExecutionStateConvergenceEvidence(
            active_states=frozenset(
                {ConvergenceState.TRAILING_ACTIVE}
            ),
            requested_states=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        ConvergenceReason.FORBIDDEN_CONVERGENCE_STATE
    )


def test_denies_unresolved_state():
    decision = evaluate_execution_state_convergence_semantics(
        topology_semantics_allowed=True,
        policy=ExecutionStateConvergencePolicy(
            required_states=frozenset(),
            forbidden_states=frozenset(),
            unresolved_states=frozenset(
                {ConvergenceState.REPLACEMENT_PENDING}
            ),
            dependency_rules=frozenset(),
            authoritative_states=frozenset(),
            stable_baseline_states=frozenset(),
        ),
        evidence=ExecutionStateConvergenceEvidence(
            active_states=frozenset(
                {ConvergenceState.REPLACEMENT_PENDING}
            ),
            requested_states=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        ConvergenceReason.UNRESOLVED_CONVERGENCE_STATE
    )


def test_denies_dependency_violation():
    rule = ConvergenceDependencyRule(
        required_state=ConvergenceState.AUTHORITATIVE_VERIFIED,
        dependent_state=ConvergenceState.CLEANUP_CONFIRMED,
    )

    decision = evaluate_execution_state_convergence_semantics(
        topology_semantics_allowed=True,
        policy=ExecutionStateConvergencePolicy(
            required_states=frozenset(),
            forbidden_states=frozenset(),
            unresolved_states=frozenset(),
            dependency_rules=frozenset({rule}),
            authoritative_states=frozenset(),
            stable_baseline_states=frozenset(),
        ),
        evidence=ExecutionStateConvergenceEvidence(
            active_states=frozenset(
                {ConvergenceState.AUTHORITATIVE_CREATED}
            ),
            requested_states=frozenset(
                {ConvergenceState.CLEANUP_CONFIRMED}
            ),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.dependency_violations == (rule,)


def test_denies_missing_authoritative_state():
    decision = evaluate_execution_state_convergence_semantics(
        topology_semantics_allowed=True,
        policy=ExecutionStateConvergencePolicy(
            required_states=frozenset(),
            forbidden_states=frozenset(),
            unresolved_states=frozenset(),
            dependency_rules=frozenset(),
            authoritative_states=frozenset(
                {ConvergenceState.AUTHORITATIVE_VERIFIED}
            ),
            stable_baseline_states=frozenset(),
        ),
        evidence=ExecutionStateConvergenceEvidence(
            active_states=frozenset(
                {ConvergenceState.AUTHORITATIVE_CREATED}
            ),
            requested_states=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        ConvergenceReason.AUTHORITATIVE_CONVERGENCE_REQUIRED
    )


def test_denies_missing_stable_baseline_state():
    decision = evaluate_execution_state_convergence_semantics(
        topology_semantics_allowed=True,
        policy=ExecutionStateConvergencePolicy(
            required_states=frozenset(),
            forbidden_states=frozenset(),
            unresolved_states=frozenset(),
            dependency_rules=frozenset(),
            authoritative_states=frozenset(),
            stable_baseline_states=frozenset(
                {ConvergenceState.STABLE_BASELINE_ESTABLISHED}
            ),
        ),
        evidence=ExecutionStateConvergenceEvidence(
            active_states=frozenset(
                {ConvergenceState.AUTHORITATIVE_VERIFIED}
            ),
            requested_states=frozenset(
                {ConvergenceState.TRAILING_ACTIVE}
            ),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        ConvergenceReason.STABLE_BASELINE_REQUIRED
    )


def test_denies_when_protection_continuity_not_proven():
    decision = evaluate_execution_state_convergence_semantics(
        topology_semantics_allowed=True,
        policy=ExecutionStateConvergencePolicy(
            required_states=frozenset(),
            forbidden_states=frozenset(),
            unresolved_states=frozenset(),
            dependency_rules=frozenset(),
            authoritative_states=frozenset(),
            stable_baseline_states=frozenset(),
            requires_protection_continuity=True,
        ),
        evidence=ExecutionStateConvergenceEvidence(
            active_states=frozenset(
                {ConvergenceState.AUTHORITATIVE_VERIFIED}
            ),
            requested_states=frozenset(
                {ConvergenceState.AUDIT_TRACE_COMPLETE}
            ),
            protection_continuity_proven=False,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        ConvergenceReason.PROTECTION_CONTINUITY_REQUIRED
    )


def test_authorizes_when_state_convergence_is_satisfied():
    cleanup_rule = ConvergenceDependencyRule(
        required_state=ConvergenceState.AUTHORITATIVE_VERIFIED,
        dependent_state=ConvergenceState.CLEANUP_CONFIRMED,
    )

    decision = evaluate_execution_state_convergence_semantics(
        topology_semantics_allowed=True,
        policy=ExecutionStateConvergencePolicy(
            required_states=frozenset(
                {
                    ConvergenceState.PROVISIONAL_PRESENT,
                    ConvergenceState.AUTHORITATIVE_VERIFIED,
                }
            ),
            forbidden_states=frozenset(),
            unresolved_states=frozenset(),
            dependency_rules=frozenset({cleanup_rule}),
            authoritative_states=frozenset(
                {ConvergenceState.AUTHORITATIVE_VERIFIED}
            ),
            stable_baseline_states=frozenset(
                {ConvergenceState.STABLE_BASELINE_ESTABLISHED}
            ),
            requires_protection_continuity=True,
        ),
        evidence=ExecutionStateConvergenceEvidence(
            active_states=frozenset(
                {
                    ConvergenceState.PROVISIONAL_PRESENT,
                    ConvergenceState.AUTHORITATIVE_VERIFIED,
                    ConvergenceState.STABLE_BASELINE_ESTABLISHED,
                }
            ),
            requested_states=frozenset(
                {
                    ConvergenceState.CLEANUP_CONFIRMED,
                    ConvergenceState.AUDIT_TRACE_COMPLETE,
                }
            ),
            protection_continuity_proven=True,
        ),
    )

    assert isinstance(
        decision,
        ExecutionStateConvergenceDecision,
    )
    assert decision.allowed is True
    assert decision.reason == ConvergenceReason.ALLOWED
