from app.protection.execution_authority_policy import (
    ExecutionAuthorityClass,
    ExecutionAuthorityEvidence,
    ExecutionAuthorityPolicy,
    ExecutionAuthorityPolicyReason,
    ExecutionIntent,
    evaluate_execution_authority_policy,
)


def test_denies_when_execution_authorization_not_allowed():
    decision = evaluate_execution_authority_policy(
        execution_authorization_allowed=False,
        policy=ExecutionAuthorityPolicy(
            required_authorities=frozenset(),
            allowed_intents=frozenset({ExecutionIntent.NOOP}),
            forbidden_intents=frozenset(),
            requires_authoritative_ownership=False,
            requires_stable_baseline=False,
            requires_protection_continuity=False,
        ),
        evidence=ExecutionAuthorityEvidence(
            granted_authorities=frozenset(),
            requested_intents=frozenset({ExecutionIntent.NOOP}),
            authoritative_ownership_proven=False,
            stable_baseline_proven=False,
            protection_continuity_proven=False,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionAuthorityPolicyReason.EXECUTION_NOT_AUTHORIZED


def test_denies_missing_required_authority():
    decision = evaluate_execution_authority_policy(
        execution_authorization_allowed=True,
        policy=ExecutionAuthorityPolicy(
            required_authorities=frozenset(
                {ExecutionAuthorityClass.REPLACEMENT_AUTHORITY}
            ),
            allowed_intents=frozenset({ExecutionIntent.REPLACE_AUTHORITATIVE_EXIT}),
            forbidden_intents=frozenset(),
        ),
        evidence=ExecutionAuthorityEvidence(
            granted_authorities=frozenset(),
            requested_intents=frozenset({ExecutionIntent.REPLACE_AUTHORITATIVE_EXIT}),
            authoritative_ownership_proven=True,
            stable_baseline_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionAuthorityPolicyReason.MISSING_REQUIRED_AUTHORITY
    assert decision.missing_authorities == (
        ExecutionAuthorityClass.REPLACEMENT_AUTHORITY,
    )


def test_denies_forbidden_intent_even_with_authority():
    decision = evaluate_execution_authority_policy(
        execution_authorization_allowed=True,
        policy=ExecutionAuthorityPolicy(
            required_authorities=frozenset(
                {ExecutionAuthorityClass.CLEANUP_AUTHORITY}
            ),
            allowed_intents=frozenset({ExecutionIntent.CLEANUP_STALE_PROVISIONAL}),
            forbidden_intents=frozenset({ExecutionIntent.CREATE_AUTHORITATIVE_EXIT}),
            requires_authoritative_ownership=False,
            requires_stable_baseline=False,
            requires_protection_continuity=True,
        ),
        evidence=ExecutionAuthorityEvidence(
            granted_authorities=frozenset(
                {ExecutionAuthorityClass.CLEANUP_AUTHORITY}
            ),
            requested_intents=frozenset({ExecutionIntent.CREATE_AUTHORITATIVE_EXIT}),
            authoritative_ownership_proven=False,
            stable_baseline_proven=False,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionAuthorityPolicyReason.FORBIDDEN_INTENT
    assert decision.forbidden_intents == (ExecutionIntent.CREATE_AUTHORITATIVE_EXIT,)


def test_denies_intent_not_explicitly_allowed():
    decision = evaluate_execution_authority_policy(
        execution_authorization_allowed=True,
        policy=ExecutionAuthorityPolicy(
            required_authorities=frozenset(
                {ExecutionAuthorityClass.PROVISIONAL_PROTECTION_AUTHORITY}
            ),
            allowed_intents=frozenset({ExecutionIntent.NOOP}),
            forbidden_intents=frozenset(),
            requires_authoritative_ownership=False,
            requires_stable_baseline=False,
            requires_protection_continuity=True,
        ),
        evidence=ExecutionAuthorityEvidence(
            granted_authorities=frozenset(
                {ExecutionAuthorityClass.PROVISIONAL_PROTECTION_AUTHORITY}
            ),
            requested_intents=frozenset({ExecutionIntent.CANCEL_PROVISIONAL_EXIT}),
            authoritative_ownership_proven=False,
            stable_baseline_proven=False,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionAuthorityPolicyReason.AUTHORITY_INTENT_MISMATCH
    assert decision.rejected_intents == (ExecutionIntent.CANCEL_PROVISIONAL_EXIT,)


def test_replacement_requires_authoritative_ownership():
    decision = evaluate_execution_authority_policy(
        execution_authorization_allowed=True,
        policy=ExecutionAuthorityPolicy(
            required_authorities=frozenset(
                {ExecutionAuthorityClass.REPLACEMENT_AUTHORITY}
            ),
            allowed_intents=frozenset({ExecutionIntent.REPLACE_AUTHORITATIVE_EXIT}),
            forbidden_intents=frozenset(),
            requires_authoritative_ownership=True,
            requires_stable_baseline=True,
            requires_protection_continuity=True,
        ),
        evidence=ExecutionAuthorityEvidence(
            granted_authorities=frozenset(
                {ExecutionAuthorityClass.REPLACEMENT_AUTHORITY}
            ),
            requested_intents=frozenset({ExecutionIntent.REPLACE_AUTHORITATIVE_EXIT}),
            authoritative_ownership_proven=False,
            stable_baseline_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == (
        ExecutionAuthorityPolicyReason.AUTHORITATIVE_OWNERSHIP_REQUIRED
    )


def test_trailing_requires_stable_baseline():
    decision = evaluate_execution_authority_policy(
        execution_authorization_allowed=True,
        policy=ExecutionAuthorityPolicy(
            required_authorities=frozenset({ExecutionAuthorityClass.TRAILING_AUTHORITY}),
            allowed_intents=frozenset({ExecutionIntent.ARM_TRAILING}),
            forbidden_intents=frozenset(),
            requires_authoritative_ownership=True,
            requires_stable_baseline=True,
            requires_protection_continuity=True,
        ),
        evidence=ExecutionAuthorityEvidence(
            granted_authorities=frozenset({ExecutionAuthorityClass.TRAILING_AUTHORITY}),
            requested_intents=frozenset({ExecutionIntent.ARM_TRAILING}),
            authoritative_ownership_proven=True,
            stable_baseline_proven=False,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionAuthorityPolicyReason.STABLE_BASELINE_REQUIRED


def test_all_execution_authority_policies_require_protection_continuity():
    decision = evaluate_execution_authority_policy(
        execution_authorization_allowed=True,
        policy=ExecutionAuthorityPolicy(
            required_authorities=frozenset(
                {ExecutionAuthorityClass.AUTHORITATIVE_PROTECTION_AUTHORITY}
            ),
            allowed_intents=frozenset({ExecutionIntent.CREATE_AUTHORITATIVE_EXIT}),
            forbidden_intents=frozenset(),
            requires_authoritative_ownership=True,
            requires_stable_baseline=True,
            requires_protection_continuity=True,
        ),
        evidence=ExecutionAuthorityEvidence(
            granted_authorities=frozenset(
                {ExecutionAuthorityClass.AUTHORITATIVE_PROTECTION_AUTHORITY}
            ),
            requested_intents=frozenset({ExecutionIntent.CREATE_AUTHORITATIVE_EXIT}),
            authoritative_ownership_proven=True,
            stable_baseline_proven=True,
            protection_continuity_proven=False,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == ExecutionAuthorityPolicyReason.PROTECTION_CONTINUITY_REQUIRED


def test_authorizes_only_when_policy_authority_and_evidence_are_satisfied():
    decision = evaluate_execution_authority_policy(
        execution_authorization_allowed=True,
        policy=ExecutionAuthorityPolicy(
            required_authorities=frozenset(
                {
                    ExecutionAuthorityClass.AUTHORITATIVE_PROTECTION_AUTHORITY,
                    ExecutionAuthorityClass.REPLACEMENT_AUTHORITY,
                }
            ),
            allowed_intents=frozenset({ExecutionIntent.REPLACE_AUTHORITATIVE_EXIT}),
            forbidden_intents=frozenset({ExecutionIntent.CANCEL_PROVISIONAL_EXIT}),
            requires_authoritative_ownership=True,
            requires_stable_baseline=True,
            requires_protection_continuity=True,
        ),
        evidence=ExecutionAuthorityEvidence(
            granted_authorities=frozenset(
                {
                    ExecutionAuthorityClass.AUTHORITATIVE_PROTECTION_AUTHORITY,
                    ExecutionAuthorityClass.REPLACEMENT_AUTHORITY,
                }
            ),
            requested_intents=frozenset({ExecutionIntent.REPLACE_AUTHORITATIVE_EXIT}),
            authoritative_ownership_proven=True,
            stable_baseline_proven=True,
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is True
    assert decision.reason == ExecutionAuthorityPolicyReason.AUTHORIZED
