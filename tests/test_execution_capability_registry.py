from app.protection.execution_capability_registry import (
    CapabilityRegistryReason,
    ExecutionCapability,
    ExecutionCapabilityRegistry,
    ExecutionCapabilityRequest,
    evaluate_execution_capability_registry,
)


def test_denies_when_authority_policy_not_allowed():
    decision = evaluate_execution_capability_registry(
        authority_policy_allowed=False,
        registry=ExecutionCapabilityRegistry(
            required_capabilities=frozenset(),
            granted_capabilities=frozenset(),
            forbidden_capabilities=frozenset(),
            incompatible_capability_sets=frozenset(),
        ),
        request=ExecutionCapabilityRequest(
            requested_capabilities=frozenset({ExecutionCapability.NOOP}),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == CapabilityRegistryReason.AUTHORITY_POLICY_NOT_ALLOWED


def test_denies_missing_required_capability():
    decision = evaluate_execution_capability_registry(
        authority_policy_allowed=True,
        registry=ExecutionCapabilityRegistry(
            required_capabilities=frozenset(
                {ExecutionCapability.CREATE_AUTHORITATIVE_EXIT}
            ),
            granted_capabilities=frozenset(),
            forbidden_capabilities=frozenset(),
            incompatible_capability_sets=frozenset(),
        ),
        request=ExecutionCapabilityRequest(
            requested_capabilities=frozenset(
                {ExecutionCapability.CREATE_AUTHORITATIVE_EXIT}
            ),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == CapabilityRegistryReason.MISSING_REQUIRED_CAPABILITY
    assert decision.missing_capabilities == (
        ExecutionCapability.CREATE_AUTHORITATIVE_EXIT,
    )


def test_denies_forbidden_capability_even_if_granted():
    decision = evaluate_execution_capability_registry(
        authority_policy_allowed=True,
        registry=ExecutionCapabilityRegistry(
            required_capabilities=frozenset(),
            granted_capabilities=frozenset(
                {ExecutionCapability.CANCEL_PROVISIONAL_EXIT}
            ),
            forbidden_capabilities=frozenset(
                {ExecutionCapability.CANCEL_PROVISIONAL_EXIT}
            ),
            incompatible_capability_sets=frozenset(),
        ),
        request=ExecutionCapabilityRequest(
            requested_capabilities=frozenset(
                {ExecutionCapability.CANCEL_PROVISIONAL_EXIT}
            ),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == CapabilityRegistryReason.FORBIDDEN_CAPABILITY
    assert decision.forbidden_capabilities == (
        ExecutionCapability.CANCEL_PROVISIONAL_EXIT,
    )


def test_denies_capability_escalation():
    decision = evaluate_execution_capability_registry(
        authority_policy_allowed=True,
        registry=ExecutionCapabilityRegistry(
            required_capabilities=frozenset(),
            granted_capabilities=frozenset({ExecutionCapability.READ_ONLY_AUDIT}),
            forbidden_capabilities=frozenset(),
            incompatible_capability_sets=frozenset(),
        ),
        request=ExecutionCapabilityRequest(
            requested_capabilities=frozenset(
                {ExecutionCapability.READ_ONLY_AUDIT, ExecutionCapability.ARM_TRAILING}
            ),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == CapabilityRegistryReason.CAPABILITY_ESCALATION
    assert decision.escalated_capabilities == (ExecutionCapability.ARM_TRAILING,)


def test_denies_incompatible_capability_set():
    incompatible_set = frozenset(
        {
            ExecutionCapability.CREATE_AUTHORITATIVE_EXIT,
            ExecutionCapability.CANCEL_PROVISIONAL_EXIT,
        }
    )

    decision = evaluate_execution_capability_registry(
        authority_policy_allowed=True,
        registry=ExecutionCapabilityRegistry(
            required_capabilities=frozenset(),
            granted_capabilities=frozenset(incompatible_set),
            forbidden_capabilities=frozenset(),
            incompatible_capability_sets=frozenset({incompatible_set}),
        ),
        request=ExecutionCapabilityRequest(
            requested_capabilities=frozenset(incompatible_set),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == CapabilityRegistryReason.INCOMPATIBLE_CAPABILITY_SET
    assert decision.incompatible_capabilities == (
        (
            ExecutionCapability.CANCEL_PROVISIONAL_EXIT,
            ExecutionCapability.CREATE_AUTHORITATIVE_EXIT,
        ),
    )


def test_denies_when_protection_continuity_not_proven():
    decision = evaluate_execution_capability_registry(
        authority_policy_allowed=True,
        registry=ExecutionCapabilityRegistry(
            required_capabilities=frozenset(),
            granted_capabilities=frozenset(
                {ExecutionCapability.CREATE_AUTHORITATIVE_EXIT}
            ),
            forbidden_capabilities=frozenset(),
            incompatible_capability_sets=frozenset(),
            requires_protection_continuity=True,
        ),
        request=ExecutionCapabilityRequest(
            requested_capabilities=frozenset(
                {ExecutionCapability.CREATE_AUTHORITATIVE_EXIT}
            ),
            protection_continuity_proven=False,
        ),
    )

    assert decision.allowed is False
    assert decision.reason == CapabilityRegistryReason.PROTECTION_CONTINUITY_REQUIRED


def test_authorizes_only_when_capability_registry_is_satisfied():
    decision = evaluate_execution_capability_registry(
        authority_policy_allowed=True,
        registry=ExecutionCapabilityRegistry(
            required_capabilities=frozenset(
                {ExecutionCapability.REPLACE_AUTHORITATIVE_EXIT}
            ),
            granted_capabilities=frozenset(
                {ExecutionCapability.REPLACE_AUTHORITATIVE_EXIT}
            ),
            forbidden_capabilities=frozenset(
                {ExecutionCapability.CANCEL_PROVISIONAL_EXIT}
            ),
            incompatible_capability_sets=frozenset(),
            requires_protection_continuity=True,
        ),
        request=ExecutionCapabilityRequest(
            requested_capabilities=frozenset(
                {ExecutionCapability.REPLACE_AUTHORITATIVE_EXIT}
            ),
            protection_continuity_proven=True,
        ),
    )

    assert decision.allowed is True
    assert decision.reason == CapabilityRegistryReason.ALLOWED
