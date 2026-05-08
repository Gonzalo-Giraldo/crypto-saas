from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Tuple


class ExecutionAuthorizationReason(str, Enum):
    AUTHORIZED = "AUTHORIZED"

    DECISION_NOT_ALLOWED = "DECISION_NOT_ALLOWED"
    MISSING_EXECUTION_PRECONDITION = "MISSING_EXECUTION_PRECONDITION"
    MISSING_RUNTIME_GUARANTEE = "MISSING_RUNTIME_GUARANTEE"
    FORBIDDEN_EXECUTION_SCOPE = "FORBIDDEN_EXECUTION_SCOPE"
    PROTECTION_CONTINUITY_NOT_PROVEN = "PROTECTION_CONTINUITY_NOT_PROVEN"
    NON_DETERMINISTIC_SCOPE = "NON_DETERMINISTIC_SCOPE"


class ExecutionScope(str, Enum):
    CREATE_AUTHORITATIVE_EXIT = "CREATE_AUTHORITATIVE_EXIT"
    CANCEL_PROVISIONAL_EXIT = "CANCEL_PROVISIONAL_EXIT"
    CLEANUP_STALE_PROVISIONAL = "CLEANUP_STALE_PROVISIONAL"
    ARM_TRAILING = "ARM_TRAILING"
    NOOP = "NOOP"


class ForbiddenExecutionScope(str, Enum):
    CANCEL_PROVISIONAL_BEFORE_AUTHORITATIVE_VERIFIED = (
        "CANCEL_PROVISIONAL_BEFORE_AUTHORITATIVE_VERIFIED"
    )
    CREATE_DUPLICATE_AUTHORITATIVE_EXIT = "CREATE_DUPLICATE_AUTHORITATIVE_EXIT"
    ARM_TRAILING_WITHOUT_STABLE_BASELINE = "ARM_TRAILING_WITHOUT_STABLE_BASELINE"
    EXECUTE_WITHOUT_RECONCILIATION_PROOF = "EXECUTE_WITHOUT_RECONCILIATION_PROOF"
    EXECUTE_RUNTIME_SIDE_EFFECT = "EXECUTE_RUNTIME_SIDE_EFFECT"


@dataclass(frozen=True)
class ExecutionAuthorizationBoundary:
    required_preconditions: FrozenSet[str]
    required_runtime_guarantees: FrozenSet[str]
    allowed_execution_scope: FrozenSet[ExecutionScope]
    forbidden_execution_scope: FrozenSet[ForbiddenExecutionScope]
    requires_protection_continuity: bool = True


@dataclass(frozen=True)
class ExecutionAuthorizationEvidence:
    satisfied_preconditions: FrozenSet[str]
    satisfied_runtime_guarantees: FrozenSet[str]
    requested_execution_scope: FrozenSet[ExecutionScope]
    observed_forbidden_scope: FrozenSet[ForbiddenExecutionScope]
    protection_continuity_proven: bool


@dataclass(frozen=True)
class ExecutionAuthorizationDecision:
    allowed: bool
    reason: ExecutionAuthorizationReason
    missing_preconditions: Tuple[str, ...]
    missing_runtime_guarantees: Tuple[str, ...]
    rejected_execution_scope: Tuple[ExecutionScope, ...]
    observed_forbidden_scope: Tuple[ForbiddenExecutionScope, ...]


def authorize_execution_boundary(
    *,
    protection_decision_allowed: bool,
    boundary: ExecutionAuthorizationBoundary,
    evidence: ExecutionAuthorizationEvidence,
) -> ExecutionAuthorizationDecision:
    """
    Pure deterministic execution authorization boundary.

    This function does not execute anything.
    It does not touch broker, Binance, DB, websocket, runtime, time, IO, or async.

    It only decides whether a previously allowed semantic protection decision
    may be handed to a future runtime execution layer.
    """

    if not protection_decision_allowed:
        return ExecutionAuthorizationDecision(
            allowed=False,
            reason=ExecutionAuthorizationReason.DECISION_NOT_ALLOWED,
            missing_preconditions=(),
            missing_runtime_guarantees=(),
            rejected_execution_scope=(),
            observed_forbidden_scope=(),
        )

    missing_preconditions = tuple(
        sorted(boundary.required_preconditions - evidence.satisfied_preconditions)
    )
    if missing_preconditions:
        return ExecutionAuthorizationDecision(
            allowed=False,
            reason=ExecutionAuthorizationReason.MISSING_EXECUTION_PRECONDITION,
            missing_preconditions=missing_preconditions,
            missing_runtime_guarantees=(),
            rejected_execution_scope=(),
            observed_forbidden_scope=(),
        )

    missing_runtime_guarantees = tuple(
        sorted(boundary.required_runtime_guarantees - evidence.satisfied_runtime_guarantees)
    )
    if missing_runtime_guarantees:
        return ExecutionAuthorizationDecision(
            allowed=False,
            reason=ExecutionAuthorizationReason.MISSING_RUNTIME_GUARANTEE,
            missing_preconditions=(),
            missing_runtime_guarantees=missing_runtime_guarantees,
            rejected_execution_scope=(),
            observed_forbidden_scope=(),
        )

    if evidence.observed_forbidden_scope:
        return ExecutionAuthorizationDecision(
            allowed=False,
            reason=ExecutionAuthorizationReason.FORBIDDEN_EXECUTION_SCOPE,
            missing_preconditions=(),
            missing_runtime_guarantees=(),
            rejected_execution_scope=(),
            observed_forbidden_scope=tuple(
                sorted(evidence.observed_forbidden_scope, key=lambda item: item.value)
            ),
        )

    rejected_execution_scope = tuple(
        sorted(
            evidence.requested_execution_scope - boundary.allowed_execution_scope,
            key=lambda item: item.value,
        )
    )
    if rejected_execution_scope:
        return ExecutionAuthorizationDecision(
            allowed=False,
            reason=ExecutionAuthorizationReason.NON_DETERMINISTIC_SCOPE,
            missing_preconditions=(),
            missing_runtime_guarantees=(),
            rejected_execution_scope=rejected_execution_scope,
            observed_forbidden_scope=(),
        )

    if boundary.requires_protection_continuity and not evidence.protection_continuity_proven:
        return ExecutionAuthorizationDecision(
            allowed=False,
            reason=ExecutionAuthorizationReason.PROTECTION_CONTINUITY_NOT_PROVEN,
            missing_preconditions=(),
            missing_runtime_guarantees=(),
            rejected_execution_scope=(),
            observed_forbidden_scope=(),
        )

    return ExecutionAuthorizationDecision(
        allowed=True,
        reason=ExecutionAuthorizationReason.AUTHORIZED,
        missing_preconditions=(),
        missing_runtime_guarantees=(),
        rejected_execution_scope=(),
        observed_forbidden_scope=(),
    )
