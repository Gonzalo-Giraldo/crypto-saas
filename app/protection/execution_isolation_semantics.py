from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Tuple


class IsolationDomain(str, Enum):
    PROVISIONAL_LIFECYCLE = "PROVISIONAL_LIFECYCLE"
    AUTHORITATIVE_LIFECYCLE = "AUTHORITATIVE_LIFECYCLE"
    REPLACEMENT_LIFECYCLE = "REPLACEMENT_LIFECYCLE"
    CLEANUP_LIFECYCLE = "CLEANUP_LIFECYCLE"
    TRAILING_LIFECYCLE = "TRAILING_LIFECYCLE"
    AUDIT_LIFECYCLE = "AUDIT_LIFECYCLE"


class IsolationViolationReason(str, Enum):
    ALLOWED = "ALLOWED"
    CAPABILITY_REGISTRY_NOT_ALLOWED = "CAPABILITY_REGISTRY_NOT_ALLOWED"
    CROSS_DOMAIN_ACCESS = "CROSS_DOMAIN_ACCESS"
    ISOLATION_BOUNDARY_VIOLATION = "ISOLATION_BOUNDARY_VIOLATION"
    FORBIDDEN_DOMAIN_INTERSECTION = "FORBIDDEN_DOMAIN_INTERSECTION"
    DOMAIN_OWNERSHIP_MISMATCH = "DOMAIN_OWNERSHIP_MISMATCH"
    PROTECTION_CONTINUITY_REQUIRED = "PROTECTION_CONTINUITY_REQUIRED"


@dataclass(frozen=True)
class ExecutionIsolationPolicy:
    allowed_domains: FrozenSet[IsolationDomain]
    forbidden_domain_intersections: FrozenSet[FrozenSet[IsolationDomain]]
    isolated_domains: FrozenSet[IsolationDomain]
    requires_domain_ownership: bool = True
    requires_protection_continuity: bool = True


@dataclass(frozen=True)
class ExecutionIsolationEvidence:
    requested_domains: FrozenSet[IsolationDomain]
    owned_domains: FrozenSet[IsolationDomain]
    protection_continuity_proven: bool


@dataclass(frozen=True)
class ExecutionIsolationDecision:
    allowed: bool
    reason: IsolationViolationReason
    rejected_domains: Tuple[IsolationDomain, ...]
    forbidden_intersections: Tuple[Tuple[IsolationDomain, ...], ...]
    ownership_violations: Tuple[IsolationDomain, ...]


def evaluate_execution_isolation_semantics(
    *,
    capability_registry_allowed: bool,
    policy: ExecutionIsolationPolicy,
    evidence: ExecutionIsolationEvidence,
) -> ExecutionIsolationDecision:
    """
    Pure deterministic execution isolation semantics evaluator.

    This function does not inspect runtime state, broker state, exchange state,
    websocket state, DB ownership, async orchestration, distributed locks, time,
    IO, or execution processes.

    It only evaluates semantic isolation boundaries for future execution layers.
    """

    if not capability_registry_allowed:
        return ExecutionIsolationDecision(
            allowed=False,
            reason=IsolationViolationReason.CAPABILITY_REGISTRY_NOT_ALLOWED,
            rejected_domains=(),
            forbidden_intersections=(),
            ownership_violations=(),
        )

    rejected_domains = tuple(
        sorted(
            evidence.requested_domains - policy.allowed_domains,
            key=lambda item: item.value,
        )
    )
    if rejected_domains:
        return ExecutionIsolationDecision(
            allowed=False,
            reason=IsolationViolationReason.CROSS_DOMAIN_ACCESS,
            rejected_domains=rejected_domains,
            forbidden_intersections=(),
            ownership_violations=(),
        )

    forbidden_intersections = tuple(
        tuple(sorted(intersection, key=lambda item: item.value))
        for intersection in sorted(
            policy.forbidden_domain_intersections,
            key=lambda item: tuple(sorted(domain.value for domain in item)),
        )
        if intersection <= evidence.requested_domains
    )
    if forbidden_intersections:
        return ExecutionIsolationDecision(
            allowed=False,
            reason=IsolationViolationReason.FORBIDDEN_DOMAIN_INTERSECTION,
            rejected_domains=(),
            forbidden_intersections=forbidden_intersections,
            ownership_violations=(),
        )

    isolated_domain_violations = tuple(
        sorted(
            (
                evidence.requested_domains & policy.isolated_domains
            ) - evidence.owned_domains,
            key=lambda item: item.value,
        )
    )
    if isolated_domain_violations:
        return ExecutionIsolationDecision(
            allowed=False,
            reason=IsolationViolationReason.ISOLATION_BOUNDARY_VIOLATION,
            rejected_domains=(),
            forbidden_intersections=(),
            ownership_violations=isolated_domain_violations,
        )

    if policy.requires_domain_ownership:
        ownership_violations = tuple(
            sorted(
                evidence.requested_domains - evidence.owned_domains,
                key=lambda item: item.value,
            )
        )
        if ownership_violations:
            return ExecutionIsolationDecision(
                allowed=False,
                reason=IsolationViolationReason.DOMAIN_OWNERSHIP_MISMATCH,
                rejected_domains=(),
                forbidden_intersections=(),
                ownership_violations=ownership_violations,
            )

    if (
        policy.requires_protection_continuity
        and not evidence.protection_continuity_proven
    ):
        return ExecutionIsolationDecision(
            allowed=False,
            reason=IsolationViolationReason.PROTECTION_CONTINUITY_REQUIRED,
            rejected_domains=(),
            forbidden_intersections=(),
            ownership_violations=(),
        )

    return ExecutionIsolationDecision(
        allowed=True,
        reason=IsolationViolationReason.ALLOWED,
        rejected_domains=(),
        forbidden_intersections=(),
        ownership_violations=(),
    )
