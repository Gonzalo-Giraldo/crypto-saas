from app.protection.execution_isolation_semantics import (
    ExecutionIsolationDecision,
    ExecutionIsolationEvidence,
    ExecutionIsolationPolicy,
    IsolationDomain,
    IsolationViolationReason,
    evaluate_execution_isolation_semantics,
)


def test_denies_when_capability_registry_not_allowed():
    decision = evaluate_execution_isolation_semantics(
        capability_registry_allowed=False,
        policy=ExecutionIsolationPolicy(
            allowed_domains=frozenset(),
            forbidden_domain_intersections=frozenset(),
            isolated_domains=frozenset(),
        ),
        evidence=ExecutionIsolationEvidence(
            requested_domains=frozenset(),
            owned_domains=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == IsolationViolationReason.CAPABILITY_REGISTRY_NOT_ALLOWED
    )


def test_denies_cross_domain_access():
    decision = evaluate_execution_isolation_semantics(
        capability_registry_allowed=True,
        policy=ExecutionIsolationPolicy(
            allowed_domains=frozenset(
                {IsolationDomain.PROVISIONAL_LIFECYCLE}
            ),
            forbidden_domain_intersections=frozenset(),
            isolated_domains=frozenset(),
        ),
        evidence=ExecutionIsolationEvidence(
            requested_domains=frozenset(
                {
                    IsolationDomain.PROVISIONAL_LIFECYCLE,
                    IsolationDomain.AUTHORITATIVE_LIFECYCLE,
                }
            ),
            owned_domains=frozenset(
                {IsolationDomain.PROVISIONAL_LIFECYCLE}
            ),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == IsolationViolationReason.CROSS_DOMAIN_ACCESS
    assert decision.rejected_domains == (
        IsolationDomain.AUTHORITATIVE_LIFECYCLE,
    )


def test_denies_forbidden_domain_intersection():
    forbidden_intersection = frozenset(
        {
            IsolationDomain.CLEANUP_LIFECYCLE,
            IsolationDomain.REPLACEMENT_LIFECYCLE,
        }
    )

    decision = evaluate_execution_isolation_semantics(
        capability_registry_allowed=True,
        policy=ExecutionIsolationPolicy(
            allowed_domains=frozenset(forbidden_intersection),
            forbidden_domain_intersections=frozenset(
                {forbidden_intersection}
            ),
            isolated_domains=frozenset(),
        ),
        evidence=ExecutionIsolationEvidence(
            requested_domains=frozenset(forbidden_intersection),
            owned_domains=frozenset(forbidden_intersection),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == IsolationViolationReason.FORBIDDEN_DOMAIN_INTERSECTION
    )


def test_denies_isolated_domain_boundary_violation():
    decision = evaluate_execution_isolation_semantics(
        capability_registry_allowed=True,
        policy=ExecutionIsolationPolicy(
            allowed_domains=frozenset(
                {IsolationDomain.TRAILING_LIFECYCLE}
            ),
            forbidden_domain_intersections=frozenset(),
            isolated_domains=frozenset(
                {IsolationDomain.TRAILING_LIFECYCLE}
            ),
        ),
        evidence=ExecutionIsolationEvidence(
            requested_domains=frozenset(
                {IsolationDomain.TRAILING_LIFECYCLE}
            ),
            owned_domains=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == IsolationViolationReason.ISOLATION_BOUNDARY_VIOLATION
    )


def test_denies_domain_ownership_mismatch():
    decision = evaluate_execution_isolation_semantics(
        capability_registry_allowed=True,
        policy=ExecutionIsolationPolicy(
            allowed_domains=frozenset(
                {
                    IsolationDomain.PROVISIONAL_LIFECYCLE,
                    IsolationDomain.AUTHORITATIVE_LIFECYCLE,
                }
            ),
            forbidden_domain_intersections=frozenset(),
            isolated_domains=frozenset(),
            requires_domain_ownership=True,
        ),
        evidence=ExecutionIsolationEvidence(
            requested_domains=frozenset(
                {
                    IsolationDomain.PROVISIONAL_LIFECYCLE,
                    IsolationDomain.AUTHORITATIVE_LIFECYCLE,
                }
            ),
            owned_domains=frozenset(
                {IsolationDomain.PROVISIONAL_LIFECYCLE}
            ),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == IsolationViolationReason.DOMAIN_OWNERSHIP_MISMATCH
    )


def test_denies_when_protection_continuity_not_proven():
    decision = evaluate_execution_isolation_semantics(
        capability_registry_allowed=True,
        policy=ExecutionIsolationPolicy(
            allowed_domains=frozenset(
                {IsolationDomain.AUTHORITATIVE_LIFECYCLE}
            ),
            forbidden_domain_intersections=frozenset(),
            isolated_domains=frozenset(),
            requires_protection_continuity=True,
        ),
        evidence=ExecutionIsolationEvidence(
            requested_domains=frozenset(
                {IsolationDomain.AUTHORITATIVE_LIFECYCLE}
            ),
            owned_domains=frozenset(
                {IsolationDomain.AUTHORITATIVE_LIFECYCLE}
            ),
            protection_continuity_proven=False,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == IsolationViolationReason.PROTECTION_CONTINUITY_REQUIRED
    )


def test_authorizes_when_isolation_semantics_are_satisfied():
    decision = evaluate_execution_isolation_semantics(
        capability_registry_allowed=True,
        policy=ExecutionIsolationPolicy(
            allowed_domains=frozenset(
                {
                    IsolationDomain.AUTHORITATIVE_LIFECYCLE,
                    IsolationDomain.REPLACEMENT_LIFECYCLE,
                }
            ),
            forbidden_domain_intersections=frozenset(),
            isolated_domains=frozenset(
                {IsolationDomain.REPLACEMENT_LIFECYCLE}
            ),
            requires_domain_ownership=True,
            requires_protection_continuity=True,
        ),
        evidence=ExecutionIsolationEvidence(
            requested_domains=frozenset(
                {
                    IsolationDomain.AUTHORITATIVE_LIFECYCLE,
                    IsolationDomain.REPLACEMENT_LIFECYCLE,
                }
            ),
            owned_domains=frozenset(
                {
                    IsolationDomain.AUTHORITATIVE_LIFECYCLE,
                    IsolationDomain.REPLACEMENT_LIFECYCLE,
                }
            ),
            protection_continuity_proven=True,
        ),
    )

    assert isinstance(decision, ExecutionIsolationDecision)
    assert decision.allowed is True
    assert decision.reason == IsolationViolationReason.ALLOWED
