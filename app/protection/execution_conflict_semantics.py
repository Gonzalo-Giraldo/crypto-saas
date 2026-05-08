from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Tuple


class ExecutionConflictDomain(str, Enum):
    PROVISIONAL_EXIT = "PROVISIONAL_EXIT"
    AUTHORITATIVE_EXIT = "AUTHORITATIVE_EXIT"
    REPLACEMENT_FLOW = "REPLACEMENT_FLOW"
    CLEANUP_FLOW = "CLEANUP_FLOW"
    TRAILING_FLOW = "TRAILING_FLOW"
    AUDIT_FLOW = "AUDIT_FLOW"


class ExecutionOperation(str, Enum):
    CREATE_AUTHORITATIVE_EXIT = "CREATE_AUTHORITATIVE_EXIT"
    REPLACE_AUTHORITATIVE_EXIT = "REPLACE_AUTHORITATIVE_EXIT"
    CANCEL_PROVISIONAL_EXIT = "CANCEL_PROVISIONAL_EXIT"
    CLEANUP_STALE_PROVISIONAL = "CLEANUP_STALE_PROVISIONAL"
    ARM_TRAILING = "ARM_TRAILING"
    READ_ONLY_AUDIT = "READ_ONLY_AUDIT"
    NOOP = "NOOP"


class ExecutionConflictReason(str, Enum):
    ALLOWED = "ALLOWED"
    ISOLATION_SEMANTICS_NOT_ALLOWED = "ISOLATION_SEMANTICS_NOT_ALLOWED"
    FORBIDDEN_OPERATION_PAIR = "FORBIDDEN_OPERATION_PAIR"
    FORBIDDEN_DOMAIN_PAIR = "FORBIDDEN_DOMAIN_PAIR"
    OPERATION_DOMAIN_CONFLICT = "OPERATION_DOMAIN_CONFLICT"
    MUTUAL_EXCLUSION_VIOLATION = "MUTUAL_EXCLUSION_VIOLATION"
    PROTECTION_CONTINUITY_REQUIRED = "PROTECTION_CONTINUITY_REQUIRED"


@dataclass(frozen=True)
class ExecutionConflictPolicy:
    forbidden_operation_pairs: FrozenSet[FrozenSet[ExecutionOperation]]
    forbidden_domain_pairs: FrozenSet[FrozenSet[ExecutionConflictDomain]]
    operation_domain_conflicts: FrozenSet[
        Tuple[ExecutionOperation, ExecutionConflictDomain]
    ]
    mutually_exclusive_operations: FrozenSet[FrozenSet[ExecutionOperation]]
    requires_protection_continuity: bool = True


@dataclass(frozen=True)
class ExecutionConflictEvidence:
    requested_operations: FrozenSet[ExecutionOperation]
    active_domains: FrozenSet[ExecutionConflictDomain]
    protection_continuity_proven: bool


@dataclass(frozen=True)
class ExecutionConflictDecision:
    allowed: bool
    reason: ExecutionConflictReason
    conflicting_operations: Tuple[Tuple[ExecutionOperation, ...], ...]
    conflicting_domains: Tuple[Tuple[ExecutionConflictDomain, ...], ...]
    operation_domain_conflicts: Tuple[
        Tuple[ExecutionOperation, ExecutionConflictDomain], ...
    ]


def _sort_operations(
    operations: FrozenSet[ExecutionOperation],
) -> Tuple[ExecutionOperation, ...]:
    return tuple(sorted(operations, key=lambda item: item.value))


def _sort_domains(
    domains: FrozenSet[ExecutionConflictDomain],
) -> Tuple[ExecutionConflictDomain, ...]:
    return tuple(sorted(domains, key=lambda item: item.value))


def evaluate_execution_conflict_semantics(
    *,
    isolation_semantics_allowed: bool,
    policy: ExecutionConflictPolicy,
    evidence: ExecutionConflictEvidence,
) -> ExecutionConflictDecision:
    """
    Pure deterministic execution conflict semantics evaluator.

    This function does not sequence execution.
    It does not lock, enqueue, retry, call broker APIs, inspect DB state,
    inspect websocket state, inspect Binance state, use time, IO, or async.

    It only evaluates semantic execution conflicts before any future runtime layer.
    """

    if not isolation_semantics_allowed:
        return ExecutionConflictDecision(
            allowed=False,
            reason=ExecutionConflictReason.ISOLATION_SEMANTICS_NOT_ALLOWED,
            conflicting_operations=(),
            conflicting_domains=(),
            operation_domain_conflicts=(),
        )

    forbidden_operation_pairs = tuple(
        _sort_operations(pair)
        for pair in sorted(
            policy.forbidden_operation_pairs,
            key=lambda item: tuple(sorted(operation.value for operation in item)),
        )
        if pair <= evidence.requested_operations
    )
    if forbidden_operation_pairs:
        return ExecutionConflictDecision(
            allowed=False,
            reason=ExecutionConflictReason.FORBIDDEN_OPERATION_PAIR,
            conflicting_operations=forbidden_operation_pairs,
            conflicting_domains=(),
            operation_domain_conflicts=(),
        )

    forbidden_domain_pairs = tuple(
        _sort_domains(pair)
        for pair in sorted(
            policy.forbidden_domain_pairs,
            key=lambda item: tuple(sorted(domain.value for domain in item)),
        )
        if pair <= evidence.active_domains
    )
    if forbidden_domain_pairs:
        return ExecutionConflictDecision(
            allowed=False,
            reason=ExecutionConflictReason.FORBIDDEN_DOMAIN_PAIR,
            conflicting_operations=(),
            conflicting_domains=forbidden_domain_pairs,
            operation_domain_conflicts=(),
        )

    operation_domain_conflicts = tuple(
        sorted(
            (
                conflict
                for conflict in policy.operation_domain_conflicts
                if conflict[0] in evidence.requested_operations
                and conflict[1] in evidence.active_domains
            ),
            key=lambda item: (item[0].value, item[1].value),
        )
    )
    if operation_domain_conflicts:
        return ExecutionConflictDecision(
            allowed=False,
            reason=ExecutionConflictReason.OPERATION_DOMAIN_CONFLICT,
            conflicting_operations=(),
            conflicting_domains=(),
            operation_domain_conflicts=operation_domain_conflicts,
        )

    mutual_exclusion_violations = tuple(
        _sort_operations(operation_set)
        for operation_set in sorted(
            policy.mutually_exclusive_operations,
            key=lambda item: tuple(sorted(operation.value for operation in item)),
        )
        if operation_set <= evidence.requested_operations
    )
    if mutual_exclusion_violations:
        return ExecutionConflictDecision(
            allowed=False,
            reason=ExecutionConflictReason.MUTUAL_EXCLUSION_VIOLATION,
            conflicting_operations=mutual_exclusion_violations,
            conflicting_domains=(),
            operation_domain_conflicts=(),
        )

    if (
        policy.requires_protection_continuity
        and not evidence.protection_continuity_proven
    ):
        return ExecutionConflictDecision(
            allowed=False,
            reason=ExecutionConflictReason.PROTECTION_CONTINUITY_REQUIRED,
            conflicting_operations=(),
            conflicting_domains=(),
            operation_domain_conflicts=(),
        )

    return ExecutionConflictDecision(
        allowed=True,
        reason=ExecutionConflictReason.ALLOWED,
        conflicting_operations=(),
        conflicting_domains=(),
        operation_domain_conflicts=(),
    )
