from app.protection.execution_topology_semantics import (
    ExecutionNode,
    ExecutionOrderingRule,
    ExecutionTopologyDecision,
    ExecutionTopologyEvidence,
    ExecutionTopologyPolicy,
    ExecutionTopologyReason,
    evaluate_execution_topology_semantics,
)


def test_denies_when_conflict_semantics_not_allowed():
    decision = evaluate_execution_topology_semantics(
        conflict_semantics_allowed=False,
        policy=ExecutionTopologyPolicy(
            required_nodes=frozenset(),
            forbidden_nodes=frozenset(),
            ordering_rules=frozenset(),
            stabilization_nodes=frozenset(),
        ),
        evidence=ExecutionTopologyEvidence(
            completed_nodes=frozenset(),
            requested_nodes=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionTopologyReason.CONFLICT_SEMANTICS_NOT_ALLOWED


def test_denies_missing_required_node():
    decision = evaluate_execution_topology_semantics(
        conflict_semantics_allowed=True,
        policy=ExecutionTopologyPolicy(
            required_nodes=frozenset({ExecutionNode.PROVISIONAL_PROTECTION_PRESENT}),
            forbidden_nodes=frozenset(),
            ordering_rules=frozenset(),
            stabilization_nodes=frozenset(),
        ),
        evidence=ExecutionTopologyEvidence(
            completed_nodes=frozenset(),
            requested_nodes=frozenset({ExecutionNode.AUTHORITATIVE_EXIT_CREATED}),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionTopologyReason.MISSING_REQUIRED_NODE
    assert decision.missing_nodes == (ExecutionNode.PROVISIONAL_PROTECTION_PRESENT,)


def test_denies_forbidden_node_present():
    decision = evaluate_execution_topology_semantics(
        conflict_semantics_allowed=True,
        policy=ExecutionTopologyPolicy(
            required_nodes=frozenset(),
            forbidden_nodes=frozenset({ExecutionNode.TRAILING_ARMED}),
            ordering_rules=frozenset(),
            stabilization_nodes=frozenset(),
        ),
        evidence=ExecutionTopologyEvidence(
            completed_nodes=frozenset({ExecutionNode.TRAILING_ARMED}),
            requested_nodes=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionTopologyReason.FORBIDDEN_NODE_PRESENT
    assert decision.forbidden_nodes == (ExecutionNode.TRAILING_ARMED,)


def test_denies_ordering_violation():
    rule = ExecutionOrderingRule(
        before=ExecutionNode.AUTHORITATIVE_EXIT_VERIFIED,
        after=ExecutionNode.PROVISIONAL_CLEANUP_AUTHORIZED,
    )

    decision = evaluate_execution_topology_semantics(
        conflict_semantics_allowed=True,
        policy=ExecutionTopologyPolicy(
            required_nodes=frozenset(),
            forbidden_nodes=frozenset(),
            ordering_rules=frozenset({rule}),
            stabilization_nodes=frozenset(),
        ),
        evidence=ExecutionTopologyEvidence(
            completed_nodes=frozenset({ExecutionNode.AUTHORITATIVE_EXIT_CREATED}),
            requested_nodes=frozenset({ExecutionNode.PROVISIONAL_CLEANUP_AUTHORIZED}),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionTopologyReason.ORDERING_VIOLATION
    assert decision.ordering_violations == (rule,)


def test_denies_when_stabilization_node_missing():
    decision = evaluate_execution_topology_semantics(
        conflict_semantics_allowed=True,
        policy=ExecutionTopologyPolicy(
            required_nodes=frozenset(),
            forbidden_nodes=frozenset(),
            ordering_rules=frozenset(),
            stabilization_nodes=frozenset(
                {ExecutionNode.STABLE_BASELINE_CONFIRMED}
            ),
        ),
        evidence=ExecutionTopologyEvidence(
            completed_nodes=frozenset({ExecutionNode.AUTHORITATIVE_EXIT_VERIFIED}),
            requested_nodes=frozenset({ExecutionNode.TRAILING_ARMED}),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionTopologyReason.STABILIZATION_REQUIRED
    assert decision.missing_stabilization_nodes == (
        ExecutionNode.STABLE_BASELINE_CONFIRMED,
    )


def test_denies_when_protection_continuity_not_proven():
    decision = evaluate_execution_topology_semantics(
        conflict_semantics_allowed=True,
        policy=ExecutionTopologyPolicy(
            required_nodes=frozenset(),
            forbidden_nodes=frozenset(),
            ordering_rules=frozenset(),
            stabilization_nodes=frozenset(),
            requires_protection_continuity=True,
        ),
        evidence=ExecutionTopologyEvidence(
            completed_nodes=frozenset({ExecutionNode.AUTHORITATIVE_EXIT_VERIFIED}),
            requested_nodes=frozenset({ExecutionNode.AUDIT_TRACE_RECORDED}),
            protection_continuity_proven=False,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionTopologyReason.PROTECTION_CONTINUITY_REQUIRED


def test_authorizes_when_topology_semantics_are_satisfied():
    cleanup_rule = ExecutionOrderingRule(
        before=ExecutionNode.AUTHORITATIVE_EXIT_VERIFIED,
        after=ExecutionNode.PROVISIONAL_CLEANUP_AUTHORIZED,
    )
    trailing_rule = ExecutionOrderingRule(
        before=ExecutionNode.STABLE_BASELINE_CONFIRMED,
        after=ExecutionNode.TRAILING_ARMED,
    )

    decision = evaluate_execution_topology_semantics(
        conflict_semantics_allowed=True,
        policy=ExecutionTopologyPolicy(
            required_nodes=frozenset(
                {
                    ExecutionNode.PROVISIONAL_PROTECTION_PRESENT,
                    ExecutionNode.AUTHORITATIVE_EXIT_VERIFIED,
                }
            ),
            forbidden_nodes=frozenset(),
            ordering_rules=frozenset({cleanup_rule, trailing_rule}),
            stabilization_nodes=frozenset(
                {ExecutionNode.STABLE_BASELINE_CONFIRMED}
            ),
            requires_protection_continuity=True,
        ),
        evidence=ExecutionTopologyEvidence(
            completed_nodes=frozenset(
                {
                    ExecutionNode.PROVISIONAL_PROTECTION_PRESENT,
                    ExecutionNode.AUTHORITATIVE_EXIT_VERIFIED,
                    ExecutionNode.STABLE_BASELINE_CONFIRMED,
                }
            ),
            requested_nodes=frozenset(
                {
                    ExecutionNode.PROVISIONAL_CLEANUP_AUTHORIZED,
                    ExecutionNode.TRAILING_ARMED,
                }
            ),
            protection_continuity_proven=True,
        ),
    )

    assert isinstance(decision, ExecutionTopologyDecision)
    assert decision.allowed is True
    assert decision.reason == ExecutionTopologyReason.ALLOWED
