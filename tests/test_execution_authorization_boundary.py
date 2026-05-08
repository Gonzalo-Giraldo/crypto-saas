from app.protection.execution_authorization_boundary import (
    ExecutionAuthorizationBoundary,
    ExecutionAuthorizationEvidence,
    ExecutionAuthorizationReason,
    ExecutionScope,
    ForbiddenExecutionScope,
    authorize_execution_boundary,
)


def test_denies_when_protection_decision_not_allowed():
    decision = authorize_execution_boundary(
        protection_decision_allowed=False,
        boundary=ExecutionAuthorizationBoundary(
            required_preconditions=frozenset(),
            required_runtime_guarantees=frozenset(),
            allowed_execution_scope=frozenset({ExecutionScope.NOOP}),
            forbidden_execution_scope=frozenset(),
        ),
        evidence=ExecutionAuthorizationEvidence(
            satisfied_preconditions=frozenset(),
            satisfied_runtime_guarantees=frozenset(),
            requested_execution_scope=frozenset({ExecutionScope.NOOP}),
            observed_forbidden_scope=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionAuthorizationReason.DECISION_NOT_ALLOWED


def test_denies_missing_execution_precondition():
    decision = authorize_execution_boundary(
        protection_decision_allowed=True,
        boundary=ExecutionAuthorizationBoundary(
            required_preconditions=frozenset({"AUTHORITATIVE_EXIT_VERIFIED"}),
            required_runtime_guarantees=frozenset(),
            allowed_execution_scope=frozenset({ExecutionScope.CANCEL_PROVISIONAL_EXIT}),
            forbidden_execution_scope=frozenset(),
        ),
        evidence=ExecutionAuthorizationEvidence(
            satisfied_preconditions=frozenset(),
            satisfied_runtime_guarantees=frozenset(),
            requested_execution_scope=frozenset({ExecutionScope.CANCEL_PROVISIONAL_EXIT}),
            observed_forbidden_scope=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionAuthorizationReason.MISSING_EXECUTION_PRECONDITION
    assert decision.missing_preconditions == ("AUTHORITATIVE_EXIT_VERIFIED",)


def test_denies_missing_runtime_guarantee():
    decision = authorize_execution_boundary(
        protection_decision_allowed=True,
        boundary=ExecutionAuthorizationBoundary(
            required_preconditions=frozenset(),
            required_runtime_guarantees=frozenset({"BROKER_ACK_REQUIRED"}),
            allowed_execution_scope=frozenset({ExecutionScope.CREATE_AUTHORITATIVE_EXIT}),
            forbidden_execution_scope=frozenset(),
        ),
        evidence=ExecutionAuthorizationEvidence(
            satisfied_preconditions=frozenset(),
            satisfied_runtime_guarantees=frozenset(),
            requested_execution_scope=frozenset({ExecutionScope.CREATE_AUTHORITATIVE_EXIT}),
            observed_forbidden_scope=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionAuthorizationReason.MISSING_RUNTIME_GUARANTEE
    assert decision.missing_runtime_guarantees == ("BROKER_ACK_REQUIRED",)


def test_denies_observed_forbidden_scope():
    decision = authorize_execution_boundary(
        protection_decision_allowed=True,
        boundary=ExecutionAuthorizationBoundary(
            required_preconditions=frozenset(),
            required_runtime_guarantees=frozenset(),
            allowed_execution_scope=frozenset({ExecutionScope.CANCEL_PROVISIONAL_EXIT}),
            forbidden_execution_scope=frozenset(),
        ),
        evidence=ExecutionAuthorizationEvidence(
            satisfied_preconditions=frozenset(),
            satisfied_runtime_guarantees=frozenset(),
            requested_execution_scope=frozenset({ExecutionScope.CANCEL_PROVISIONAL_EXIT}),
            observed_forbidden_scope=frozenset(
                {
                    ForbiddenExecutionScope.CANCEL_PROVISIONAL_BEFORE_AUTHORITATIVE_VERIFIED
                }
            ),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionAuthorizationReason.FORBIDDEN_EXECUTION_SCOPE


def test_denies_scope_not_explicitly_allowed():
    decision = authorize_execution_boundary(
        protection_decision_allowed=True,
        boundary=ExecutionAuthorizationBoundary(
            required_preconditions=frozenset(),
            required_runtime_guarantees=frozenset(),
            allowed_execution_scope=frozenset({ExecutionScope.NOOP}),
            forbidden_execution_scope=frozenset(),
        ),
        evidence=ExecutionAuthorizationEvidence(
            satisfied_preconditions=frozenset(),
            satisfied_runtime_guarantees=frozenset(),
            requested_execution_scope=frozenset({ExecutionScope.ARM_TRAILING}),
            observed_forbidden_scope=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionAuthorizationReason.NON_DETERMINISTIC_SCOPE
    assert decision.rejected_execution_scope == (ExecutionScope.ARM_TRAILING,)


def test_denies_when_protection_continuity_not_proven():
    decision = authorize_execution_boundary(
        protection_decision_allowed=True,
        boundary=ExecutionAuthorizationBoundary(
            required_preconditions=frozenset(),
            required_runtime_guarantees=frozenset(),
            allowed_execution_scope=frozenset({ExecutionScope.CREATE_AUTHORITATIVE_EXIT}),
            forbidden_execution_scope=frozenset(),
            requires_protection_continuity=True,
        ),
        evidence=ExecutionAuthorizationEvidence(
            satisfied_preconditions=frozenset(),
            satisfied_runtime_guarantees=frozenset(),
            requested_execution_scope=frozenset({ExecutionScope.CREATE_AUTHORITATIVE_EXIT}),
            observed_forbidden_scope=frozenset(),
            protection_continuity_proven=False,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionAuthorizationReason.PROTECTION_CONTINUITY_NOT_PROVEN


def test_authorizes_only_when_all_boundaries_are_satisfied():
    decision = authorize_execution_boundary(
        protection_decision_allowed=True,
        boundary=ExecutionAuthorizationBoundary(
            required_preconditions=frozenset({"AUTHORITATIVE_EXIT_VERIFIED"}),
            required_runtime_guarantees=frozenset({"BROKER_ACK_REQUIRED"}),
            allowed_execution_scope=frozenset({ExecutionScope.CANCEL_PROVISIONAL_EXIT}),
            forbidden_execution_scope=frozenset(),
            requires_protection_continuity=True,
        ),
        evidence=ExecutionAuthorizationEvidence(
            satisfied_preconditions=frozenset({"AUTHORITATIVE_EXIT_VERIFIED"}),
            satisfied_runtime_guarantees=frozenset({"BROKER_ACK_REQUIRED"}),
            requested_execution_scope=frozenset({ExecutionScope.CANCEL_PROVISIONAL_EXIT}),
            observed_forbidden_scope=frozenset(),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is True
    assert decision.reason == ExecutionAuthorizationReason.AUTHORIZED
