from app.protection.execution_conflict_semantics import (
    ExecutionConflictDecision,
    ExecutionConflictDomain,
    ExecutionConflictEvidence,
    ExecutionConflictPolicy,
    ExecutionConflictReason,
    ExecutionOperation,
    evaluate_execution_conflict_semantics,
)


def test_denies_when_isolation_semantics_not_allowed():
    decision = evaluate_execution_conflict_semantics(
        isolation_semantics_allowed=False,
        policy=ExecutionConflictPolicy(
            forbidden_operation_pairs=frozenset(),
            forbidden_domain_pairs=frozenset(),
            operation_domain_conflicts=frozenset(),
            mutually_exclusive_operations=frozenset(),
        ),
        evidence=ExecutionConflictEvidence(
            requested_operations=frozenset(),
            active_domains=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionConflictReason.ISOLATION_SEMANTICS_NOT_ALLOWED


def test_denies_forbidden_operation_pair():
    forbidden_pair = frozenset(
        {
            ExecutionOperation.CREATE_AUTHORITATIVE_EXIT,
            ExecutionOperation.CANCEL_PROVISIONAL_EXIT,
        }
    )

    decision = evaluate_execution_conflict_semantics(
        isolation_semantics_allowed=True,
        policy=ExecutionConflictPolicy(
            forbidden_operation_pairs=frozenset({forbidden_pair}),
            forbidden_domain_pairs=frozenset(),
            operation_domain_conflicts=frozenset(),
            mutually_exclusive_operations=frozenset(),
        ),
        evidence=ExecutionConflictEvidence(
            requested_operations=frozenset(forbidden_pair),
            active_domains=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionConflictReason.FORBIDDEN_OPERATION_PAIR


def test_denies_forbidden_domain_pair():
    forbidden_pair = frozenset(
        {
            ExecutionConflictDomain.CLEANUP_FLOW,
            ExecutionConflictDomain.REPLACEMENT_FLOW,
        }
    )

    decision = evaluate_execution_conflict_semantics(
        isolation_semantics_allowed=True,
        policy=ExecutionConflictPolicy(
            forbidden_operation_pairs=frozenset(),
            forbidden_domain_pairs=frozenset({forbidden_pair}),
            operation_domain_conflicts=frozenset(),
            mutually_exclusive_operations=frozenset(),
        ),
        evidence=ExecutionConflictEvidence(
            requested_operations=frozenset({ExecutionOperation.NOOP}),
            active_domains=frozenset(forbidden_pair),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionConflictReason.FORBIDDEN_DOMAIN_PAIR


def test_denies_operation_domain_conflict():
    conflict = (
        ExecutionOperation.ARM_TRAILING,
        ExecutionConflictDomain.REPLACEMENT_FLOW,
    )

    decision = evaluate_execution_conflict_semantics(
        isolation_semantics_allowed=True,
        policy=ExecutionConflictPolicy(
            forbidden_operation_pairs=frozenset(),
            forbidden_domain_pairs=frozenset(),
            operation_domain_conflicts=frozenset({conflict}),
            mutually_exclusive_operations=frozenset(),
        ),
        evidence=ExecutionConflictEvidence(
            requested_operations=frozenset({ExecutionOperation.ARM_TRAILING}),
            active_domains=frozenset({ExecutionConflictDomain.REPLACEMENT_FLOW}),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionConflictReason.OPERATION_DOMAIN_CONFLICT
    assert decision.operation_domain_conflicts == (conflict,)


def test_denies_mutual_exclusion_violation():
    mutually_exclusive = frozenset(
        {
            ExecutionOperation.REPLACE_AUTHORITATIVE_EXIT,
            ExecutionOperation.ARM_TRAILING,
        }
    )

    decision = evaluate_execution_conflict_semantics(
        isolation_semantics_allowed=True,
        policy=ExecutionConflictPolicy(
            forbidden_operation_pairs=frozenset(),
            forbidden_domain_pairs=frozenset(),
            operation_domain_conflicts=frozenset(),
            mutually_exclusive_operations=frozenset({mutually_exclusive}),
        ),
        evidence=ExecutionConflictEvidence(
            requested_operations=frozenset(mutually_exclusive),
            active_domains=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionConflictReason.MUTUAL_EXCLUSION_VIOLATION


def test_denies_when_protection_continuity_not_proven():
    decision = evaluate_execution_conflict_semantics(
        isolation_semantics_allowed=True,
        policy=ExecutionConflictPolicy(
            forbidden_operation_pairs=frozenset(),
            forbidden_domain_pairs=frozenset(),
            operation_domain_conflicts=frozenset(),
            mutually_exclusive_operations=frozenset(),
            requires_protection_continuity=True,
        ),
        evidence=ExecutionConflictEvidence(
            requested_operations=frozenset({ExecutionOperation.READ_ONLY_AUDIT}),
            active_domains=frozenset({ExecutionConflictDomain.AUDIT_FLOW}),
            protection_continuity_proven=False,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionConflictReason.PROTECTION_CONTINUITY_REQUIRED


def test_authorizes_when_no_conflicts_exist():
    decision = evaluate_execution_conflict_semantics(
        isolation_semantics_allowed=True,
        policy=ExecutionConflictPolicy(
            forbidden_operation_pairs=frozenset(
                {
                    frozenset(
                        {
                            ExecutionOperation.CREATE_AUTHORITATIVE_EXIT,
                            ExecutionOperation.CANCEL_PROVISIONAL_EXIT,
                        }
                    )
                }
            ),
            forbidden_domain_pairs=frozenset(
                {
                    frozenset(
                        {
                            ExecutionConflictDomain.CLEANUP_FLOW,
                            ExecutionConflictDomain.REPLACEMENT_FLOW,
                        }
                    )
                }
            ),
            operation_domain_conflicts=frozenset(
                {
                    (
                        ExecutionOperation.ARM_TRAILING,
                        ExecutionConflictDomain.REPLACEMENT_FLOW,
                    )
                }
            ),
            mutually_exclusive_operations=frozenset(
                {
                    frozenset(
                        {
                            ExecutionOperation.REPLACE_AUTHORITATIVE_EXIT,
                            ExecutionOperation.ARM_TRAILING,
                        }
                    )
                }
            ),
            requires_protection_continuity=True,
        ),
        evidence=ExecutionConflictEvidence(
            requested_operations=frozenset({ExecutionOperation.READ_ONLY_AUDIT}),
            active_domains=frozenset({ExecutionConflictDomain.AUDIT_FLOW}),
            protection_continuity_proven=True,
        ),
    )

    assert isinstance(decision, ExecutionConflictDecision)
    assert decision.allowed is True
    assert decision.reason == ExecutionConflictReason.ALLOWED
