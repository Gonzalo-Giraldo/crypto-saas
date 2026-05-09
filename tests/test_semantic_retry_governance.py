from app.protection.semantic_retry_governance import (
    RetryAction,
    RetryBoundary,
    RetryEvidenceRequirement,
    RetryGovernanceReason,
    SemanticRetryDecision,
    SemanticRetryEvidence,
    SemanticRetryPolicy,
    evaluate_semantic_retry_governance,
)


def test_denies_when_recovery_governance_not_allowed():
    decision = evaluate_semantic_retry_governance(
        recovery_governance_allowed=False,
        policy=SemanticRetryPolicy(
            allowed_retry_actions=frozenset({RetryAction.NOOP}),
            forbidden_retry_actions=frozenset(),
            allowed_boundaries=frozenset(
                {RetryBoundary.AUDIT_REPLAY_BOUNDARY}
            ),
            forbidden_boundaries=frozenset(),
            required_retry_evidence=frozenset(),
            post_finality_forbidden_boundaries=frozenset(),
        ),
        evidence=SemanticRetryEvidence(
            requested_retry_action=RetryAction.NOOP,
            requested_boundary=RetryBoundary.AUDIT_REPLAY_BOUNDARY,
            provided_retry_evidence=frozenset(),
            idempotency_proven=True,
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == RetryGovernanceReason.RECOVERY_GOVERNANCE_NOT_ALLOWED
    )


def test_denies_forbidden_retry_action():
    decision = evaluate_semantic_retry_governance(
        recovery_governance_allowed=True,
        policy=SemanticRetryPolicy(
            allowed_retry_actions=frozenset(
                {RetryAction.RETRY_AUDIT_REPLAY}
            ),
            forbidden_retry_actions=frozenset(
                {RetryAction.RETRY_CLEANUP}
            ),
            allowed_boundaries=frozenset(
                {RetryBoundary.CLEANUP_BOUNDARY}
            ),
            forbidden_boundaries=frozenset(),
            required_retry_evidence=frozenset(),
            post_finality_forbidden_boundaries=frozenset(),
        ),
        evidence=SemanticRetryEvidence(
            requested_retry_action=RetryAction.RETRY_CLEANUP,
            requested_boundary=RetryBoundary.CLEANUP_BOUNDARY,
            provided_retry_evidence=frozenset(),
            idempotency_proven=True,
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        RetryGovernanceReason.FORBIDDEN_RETRY_ACTION
    )


def test_denies_non_allowed_retry_action():
    decision = evaluate_semantic_retry_governance(
        recovery_governance_allowed=True,
        policy=SemanticRetryPolicy(
            allowed_retry_actions=frozenset(
                {RetryAction.RETRY_AUDIT_REPLAY}
            ),
            forbidden_retry_actions=frozenset(),
            allowed_boundaries=frozenset(
                {RetryBoundary.AUDIT_REPLAY_BOUNDARY}
            ),
            forbidden_boundaries=frozenset(),
            required_retry_evidence=frozenset(),
            post_finality_forbidden_boundaries=frozenset(),
        ),
        evidence=SemanticRetryEvidence(
            requested_retry_action=(
                RetryAction.RETRY_RECONCILIATION
            ),
            requested_boundary=(
                RetryBoundary.AUDIT_REPLAY_BOUNDARY
            ),
            provided_retry_evidence=frozenset(),
            idempotency_proven=True,
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        RetryGovernanceReason.FORBIDDEN_RETRY_ACTION
    )


def test_denies_forbidden_retry_boundary():
    decision = evaluate_semantic_retry_governance(
        recovery_governance_allowed=True,
        policy=SemanticRetryPolicy(
            allowed_retry_actions=frozenset(
                {RetryAction.RETRY_RECONCILIATION}
            ),
            forbidden_retry_actions=frozenset(),
            allowed_boundaries=frozenset(
                {RetryBoundary.PRE_FINALITY}
            ),
            forbidden_boundaries=frozenset(
                {RetryBoundary.POST_FINALITY}
            ),
            required_retry_evidence=frozenset(),
            post_finality_forbidden_boundaries=frozenset(),
        ),
        evidence=SemanticRetryEvidence(
            requested_retry_action=(
                RetryAction.RETRY_RECONCILIATION
            ),
            requested_boundary=(
                RetryBoundary.POST_FINALITY
            ),
            provided_retry_evidence=frozenset(),
            idempotency_proven=True,
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        RetryGovernanceReason.FORBIDDEN_RETRY_BOUNDARY
    )


def test_denies_post_finality_retry_violation():
    decision = evaluate_semantic_retry_governance(
        recovery_governance_allowed=True,
        policy=SemanticRetryPolicy(
            allowed_retry_actions=frozenset(
                {RetryAction.RETRY_RECONCILIATION}
            ),
            forbidden_retry_actions=frozenset(),
            allowed_boundaries=frozenset(
                {RetryBoundary.POST_FINALITY}
            ),
            forbidden_boundaries=frozenset(),
            required_retry_evidence=frozenset(),
            post_finality_forbidden_boundaries=frozenset(
                {RetryBoundary.POST_FINALITY}
            ),
        ),
        evidence=SemanticRetryEvidence(
            requested_retry_action=(
                RetryAction.RETRY_RECONCILIATION
            ),
            requested_boundary=(
                RetryBoundary.POST_FINALITY
            ),
            provided_retry_evidence=frozenset(),
            idempotency_proven=True,
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        RetryGovernanceReason.POST_FINALITY_RETRY_VIOLATION
    )


def test_denies_missing_retry_evidence():
    decision = evaluate_semantic_retry_governance(
        recovery_governance_allowed=True,
        policy=SemanticRetryPolicy(
            allowed_retry_actions=frozenset(
                {RetryAction.RETRY_AUDIT_REPLAY}
            ),
            forbidden_retry_actions=frozenset(),
            allowed_boundaries=frozenset(
                {RetryBoundary.AUDIT_REPLAY_BOUNDARY}
            ),
            forbidden_boundaries=frozenset(),
            required_retry_evidence=frozenset(
                {
                    RetryEvidenceRequirement.RETRY_TRACE_PRESENT,
                    RetryEvidenceRequirement.IDEMPOTENCY_PROVEN,
                }
            ),
            post_finality_forbidden_boundaries=frozenset(),
        ),
        evidence=SemanticRetryEvidence(
            requested_retry_action=(
                RetryAction.RETRY_AUDIT_REPLAY
            ),
            requested_boundary=(
                RetryBoundary.AUDIT_REPLAY_BOUNDARY
            ),
            provided_retry_evidence=frozenset(
                {
                    RetryEvidenceRequirement.RETRY_TRACE_PRESENT
                }
            ),
            idempotency_proven=True,
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        RetryGovernanceReason.MISSING_RETRY_EVIDENCE
    )


def test_denies_when_idempotency_not_proven():
    decision = evaluate_semantic_retry_governance(
        recovery_governance_allowed=True,
        policy=SemanticRetryPolicy(
            allowed_retry_actions=frozenset(
                {RetryAction.RETRY_RECONCILIATION}
            ),
            forbidden_retry_actions=frozenset(),
            allowed_boundaries=frozenset(
                {RetryBoundary.CONVERGENCE_BOUNDARY}
            ),
            forbidden_boundaries=frozenset(),
            required_retry_evidence=frozenset(),
            post_finality_forbidden_boundaries=frozenset(),
            idempotency_required=True,
        ),
        evidence=SemanticRetryEvidence(
            requested_retry_action=(
                RetryAction.RETRY_RECONCILIATION
            ),
            requested_boundary=(
                RetryBoundary.CONVERGENCE_BOUNDARY
            ),
            provided_retry_evidence=frozenset(),
            idempotency_proven=False,
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        RetryGovernanceReason.IDEMPOTENCY_REQUIRED
    )


def test_denies_when_replay_not_proven():
    decision = evaluate_semantic_retry_governance(
        recovery_governance_allowed=True,
        policy=SemanticRetryPolicy(
            allowed_retry_actions=frozenset(
                {RetryAction.RETRY_AUDIT_REPLAY}
            ),
            forbidden_retry_actions=frozenset(),
            allowed_boundaries=frozenset(
                {RetryBoundary.AUDIT_REPLAY_BOUNDARY}
            ),
            forbidden_boundaries=frozenset(),
            required_retry_evidence=frozenset(),
            post_finality_forbidden_boundaries=frozenset(),
            replay_required=True,
        ),
        evidence=SemanticRetryEvidence(
            requested_retry_action=(
                RetryAction.RETRY_AUDIT_REPLAY
            ),
            requested_boundary=(
                RetryBoundary.AUDIT_REPLAY_BOUNDARY
            ),
            provided_retry_evidence=frozenset(),
            idempotency_proven=True,
            replay_determinism_proven=False,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        RetryGovernanceReason.REPLAY_DETERMINISM_REQUIRED
    )


def test_denies_when_protection_continuity_not_proven():
    decision = evaluate_semantic_retry_governance(
        recovery_governance_allowed=True,
        policy=SemanticRetryPolicy(
            allowed_retry_actions=frozenset(
                {RetryAction.RETRY_CONVERGENCE_VALIDATION}
            ),
            forbidden_retry_actions=frozenset(),
            allowed_boundaries=frozenset(
                {RetryBoundary.CONVERGENCE_BOUNDARY}
            ),
            forbidden_boundaries=frozenset(),
            required_retry_evidence=frozenset(),
            post_finality_forbidden_boundaries=frozenset(),
            requires_protection_continuity=True,
        ),
        evidence=SemanticRetryEvidence(
            requested_retry_action=(
                RetryAction.RETRY_CONVERGENCE_VALIDATION
            ),
            requested_boundary=(
                RetryBoundary.CONVERGENCE_BOUNDARY
            ),
            provided_retry_evidence=frozenset(),
            idempotency_proven=True,
            replay_determinism_proven=True,
            protection_continuity_proven=False,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        RetryGovernanceReason.PROTECTION_CONTINUITY_REQUIRED
    )


def test_authorizes_retry_when_governance_is_satisfied():
    decision = evaluate_semantic_retry_governance(
        recovery_governance_allowed=True,
        policy=SemanticRetryPolicy(
            allowed_retry_actions=frozenset(
                {
                    RetryAction.RETRY_RECONCILIATION,
                    RetryAction.RETRY_CONVERGENCE_VALIDATION,
                }
            ),
            forbidden_retry_actions=frozenset(),
            allowed_boundaries=frozenset(
                {
                    RetryBoundary.CONVERGENCE_BOUNDARY,
                    RetryBoundary.AUDIT_REPLAY_BOUNDARY,
                }
            ),
            forbidden_boundaries=frozenset(),
            required_retry_evidence=frozenset(
                {
                    RetryEvidenceRequirement.RETRY_TRACE_PRESENT,
                    RetryEvidenceRequirement.IDEMPOTENCY_PROVEN,
                    RetryEvidenceRequirement.REPLAY_DETERMINISM_PROVEN,
                    RetryEvidenceRequirement.PROTECTION_CONTINUITY_PROVEN,
                }
            ),
            post_finality_forbidden_boundaries=frozenset(),
            idempotency_required=True,
            replay_required=True,
            requires_protection_continuity=True,
        ),
        evidence=SemanticRetryEvidence(
            requested_retry_action=(
                RetryAction.RETRY_RECONCILIATION
            ),
            requested_boundary=(
                RetryBoundary.CONVERGENCE_BOUNDARY
            ),
            provided_retry_evidence=frozenset(
                {
                    RetryEvidenceRequirement.RETRY_TRACE_PRESENT,
                    RetryEvidenceRequirement.IDEMPOTENCY_PROVEN,
                    RetryEvidenceRequirement.REPLAY_DETERMINISM_PROVEN,
                    RetryEvidenceRequirement.PROTECTION_CONTINUITY_PROVEN,
                }
            ),
            idempotency_proven=True,
            replay_determinism_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert isinstance(decision, SemanticRetryDecision)
    assert decision.allowed is True
    assert decision.reason == RetryGovernanceReason.ALLOWED
    assert decision.retry_action == (
        RetryAction.RETRY_RECONCILIATION
    )
