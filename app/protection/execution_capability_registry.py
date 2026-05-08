from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Tuple


class ExecutionCapability(str, Enum):
    CREATE_AUTHORITATIVE_EXIT = "CREATE_AUTHORITATIVE_EXIT"
    REPLACE_AUTHORITATIVE_EXIT = "REPLACE_AUTHORITATIVE_EXIT"
    CANCEL_PROVISIONAL_EXIT = "CANCEL_PROVISIONAL_EXIT"
    CLEANUP_STALE_PROVISIONAL = "CLEANUP_STALE_PROVISIONAL"
    ARM_TRAILING = "ARM_TRAILING"
    READ_ONLY_AUDIT = "READ_ONLY_AUDIT"
    NOOP = "NOOP"


class CapabilityRegistryReason(str, Enum):
    ALLOWED = "ALLOWED"
    AUTHORITY_POLICY_NOT_ALLOWED = "AUTHORITY_POLICY_NOT_ALLOWED"
    MISSING_REQUIRED_CAPABILITY = "MISSING_REQUIRED_CAPABILITY"
    FORBIDDEN_CAPABILITY = "FORBIDDEN_CAPABILITY"
    CAPABILITY_ESCALATION = "CAPABILITY_ESCALATION"
    INCOMPATIBLE_CAPABILITY_SET = "INCOMPATIBLE_CAPABILITY_SET"
    PROTECTION_CONTINUITY_REQUIRED = "PROTECTION_CONTINUITY_REQUIRED"


@dataclass(frozen=True)
class ExecutionCapabilityRegistry:
    required_capabilities: FrozenSet[ExecutionCapability]
    granted_capabilities: FrozenSet[ExecutionCapability]
    forbidden_capabilities: FrozenSet[ExecutionCapability]
    incompatible_capability_sets: FrozenSet[FrozenSet[ExecutionCapability]]
    requires_protection_continuity: bool = True


@dataclass(frozen=True)
class ExecutionCapabilityRequest:
    requested_capabilities: FrozenSet[ExecutionCapability]
    protection_continuity_proven: bool


@dataclass(frozen=True)
class ExecutionCapabilityDecision:
    allowed: bool
    reason: CapabilityRegistryReason
    missing_capabilities: Tuple[ExecutionCapability, ...]
    forbidden_capabilities: Tuple[ExecutionCapability, ...]
    escalated_capabilities: Tuple[ExecutionCapability, ...]
    incompatible_capabilities: Tuple[Tuple[ExecutionCapability, ...], ...]


def evaluate_execution_capability_registry(
    *,
    authority_policy_allowed: bool,
    registry: ExecutionCapabilityRegistry,
    request: ExecutionCapabilityRequest,
) -> ExecutionCapabilityDecision:
    """
    Pure deterministic execution capability registry evaluator.

    This function does not execute anything.
    It does not authenticate users.
    It does not inspect runtime, broker, Binance, websocket, DB, time, IO, or async.

    It only checks whether a semantically authorized execution request has the
    explicit capabilities required for a future execution layer.
    """

    if not authority_policy_allowed:
        return ExecutionCapabilityDecision(
            allowed=False,
            reason=CapabilityRegistryReason.AUTHORITY_POLICY_NOT_ALLOWED,
            missing_capabilities=(),
            forbidden_capabilities=(),
            escalated_capabilities=(),
            incompatible_capabilities=(),
        )

    missing_capabilities = tuple(
        sorted(
            registry.required_capabilities - registry.granted_capabilities,
            key=lambda item: item.value,
        )
    )
    if missing_capabilities:
        return ExecutionCapabilityDecision(
            allowed=False,
            reason=CapabilityRegistryReason.MISSING_REQUIRED_CAPABILITY,
            missing_capabilities=missing_capabilities,
            forbidden_capabilities=(),
            escalated_capabilities=(),
            incompatible_capabilities=(),
        )

    forbidden_capabilities = tuple(
        sorted(
            request.requested_capabilities & registry.forbidden_capabilities,
            key=lambda item: item.value,
        )
    )
    if forbidden_capabilities:
        return ExecutionCapabilityDecision(
            allowed=False,
            reason=CapabilityRegistryReason.FORBIDDEN_CAPABILITY,
            missing_capabilities=(),
            forbidden_capabilities=forbidden_capabilities,
            escalated_capabilities=(),
            incompatible_capabilities=(),
        )

    escalated_capabilities = tuple(
        sorted(
            request.requested_capabilities - registry.granted_capabilities,
            key=lambda item: item.value,
        )
    )
    if escalated_capabilities:
        return ExecutionCapabilityDecision(
            allowed=False,
            reason=CapabilityRegistryReason.CAPABILITY_ESCALATION,
            missing_capabilities=(),
            forbidden_capabilities=(),
            escalated_capabilities=escalated_capabilities,
            incompatible_capabilities=(),
        )

    incompatible_capabilities = tuple(
        tuple(sorted(capability_set, key=lambda item: item.value))
        for capability_set in sorted(
            registry.incompatible_capability_sets,
            key=lambda item: tuple(sorted(capability.value for capability in item)),
        )
        if capability_set <= request.requested_capabilities
    )
    if incompatible_capabilities:
        return ExecutionCapabilityDecision(
            allowed=False,
            reason=CapabilityRegistryReason.INCOMPATIBLE_CAPABILITY_SET,
            missing_capabilities=(),
            forbidden_capabilities=(),
            escalated_capabilities=(),
            incompatible_capabilities=incompatible_capabilities,
        )

    if registry.requires_protection_continuity and not request.protection_continuity_proven:
        return ExecutionCapabilityDecision(
            allowed=False,
            reason=CapabilityRegistryReason.PROTECTION_CONTINUITY_REQUIRED,
            missing_capabilities=(),
            forbidden_capabilities=(),
            escalated_capabilities=(),
            incompatible_capabilities=(),
        )

    return ExecutionCapabilityDecision(
        allowed=True,
        reason=CapabilityRegistryReason.ALLOWED,
        missing_capabilities=(),
        forbidden_capabilities=(),
        escalated_capabilities=(),
        incompatible_capabilities=(),
    )
