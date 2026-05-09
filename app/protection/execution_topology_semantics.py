from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Tuple


class ExecutionNode(str, Enum):
    PROVISIONAL_PROTECTION_PRESENT = "PROVISIONAL_PROTECTION_PRESENT"
    AUTHORITATIVE_EXIT_CREATED = "AUTHORITATIVE_EXIT_CREATED"
    AUTHORITATIVE_EXIT_VERIFIED = "AUTHORITATIVE_EXIT_VERIFIED"
    REPLACEMENT_RECONCILED = "REPLACEMENT_RECONCILED"
    PROVISIONAL_CLEANUP_AUTHORIZED = "PROVISIONAL_CLEANUP_AUTHORIZED"
    PROVISIONAL_CLEANUP_CONFIRMED = "PROVISIONAL_CLEANUP_CONFIRMED"
    STABLE_BASELINE_CONFIRMED = "STABLE_BASELINE_CONFIRMED"
    TRAILING_ARMED = "TRAILING_ARMED"
    AUDIT_TRACE_RECORDED = "AUDIT_TRACE_RECORDED"


class ExecutionTopologyReason(str, Enum):
    ALLOWED = "ALLOWED"
    CONFLICT_SEMANTICS_NOT_ALLOWED = "CONFLICT_SEMANTICS_NOT_ALLOWED"
    MISSING_REQUIRED_NODE = "MISSING_REQUIRED_NODE"
    FORBIDDEN_NODE_PRESENT = "FORBIDDEN_NODE_PRESENT"
    ORDERING_VIOLATION = "ORDERING_VIOLATION"
    STABILIZATION_REQUIRED = "STABILIZATION_REQUIRED"
    PROTECTION_CONTINUITY_REQUIRED = "PROTECTION_CONTINUITY_REQUIRED"


@dataclass(frozen=True)
class ExecutionOrderingRule:
    before: ExecutionNode
    after: ExecutionNode


@dataclass(frozen=True)
class ExecutionTopologyPolicy:
    required_nodes: FrozenSet[ExecutionNode]
    forbidden_nodes: FrozenSet[ExecutionNode]
    ordering_rules: FrozenSet[ExecutionOrderingRule]
    stabilization_nodes: FrozenSet[ExecutionNode]
    requires_protection_continuity: bool = True


@dataclass(frozen=True)
class ExecutionTopologyEvidence:
    completed_nodes: FrozenSet[ExecutionNode]
    requested_nodes: FrozenSet[ExecutionNode]
    protection_continuity_proven: bool


@dataclass(frozen=True)
class ExecutionTopologyDecision:
    allowed: bool
    reason: ExecutionTopologyReason
    missing_nodes: Tuple[ExecutionNode, ...]
    forbidden_nodes: Tuple[ExecutionNode, ...]
    ordering_violations: Tuple[ExecutionOrderingRule, ...]
    missing_stabilization_nodes: Tuple[ExecutionNode, ...]


def evaluate_execution_topology_semantics(
    *,
    conflict_semantics_allowed: bool,
    policy: ExecutionTopologyPolicy,
    evidence: ExecutionTopologyEvidence,
) -> ExecutionTopologyDecision:
    """
    Pure deterministic execution topology semantics evaluator.

    This function does not execute, schedule, retry, lock, persist, call broker APIs,
    call Binance APIs, inspect websocket state, inspect DB state, use time, IO, or async.

    It only evaluates whether a future execution graph is semantically legal.
    """

    if not conflict_semantics_allowed:
        return ExecutionTopologyDecision(
            allowed=False,
            reason=ExecutionTopologyReason.CONFLICT_SEMANTICS_NOT_ALLOWED,
            missing_nodes=(),
            forbidden_nodes=(),
            ordering_violations=(),
            missing_stabilization_nodes=(),
        )

    available_nodes = evidence.completed_nodes | evidence.requested_nodes

    missing_nodes = tuple(
        sorted(
            policy.required_nodes - available_nodes,
            key=lambda item: item.value,
        )
    )
    if missing_nodes:
        return ExecutionTopologyDecision(
            allowed=False,
            reason=ExecutionTopologyReason.MISSING_REQUIRED_NODE,
            missing_nodes=missing_nodes,
            forbidden_nodes=(),
            ordering_violations=(),
            missing_stabilization_nodes=(),
        )

    forbidden_nodes = tuple(
        sorted(
            available_nodes & policy.forbidden_nodes,
            key=lambda item: item.value,
        )
    )
    if forbidden_nodes:
        return ExecutionTopologyDecision(
            allowed=False,
            reason=ExecutionTopologyReason.FORBIDDEN_NODE_PRESENT,
            missing_nodes=(),
            forbidden_nodes=forbidden_nodes,
            ordering_violations=(),
            missing_stabilization_nodes=(),
        )

    ordering_violations = tuple(
        sorted(
            (
                rule
                for rule in policy.ordering_rules
                if rule.after in evidence.requested_nodes
                and rule.before not in evidence.completed_nodes
            ),
            key=lambda rule: (rule.before.value, rule.after.value),
        )
    )
    if ordering_violations:
        return ExecutionTopologyDecision(
            allowed=False,
            reason=ExecutionTopologyReason.ORDERING_VIOLATION,
            missing_nodes=(),
            forbidden_nodes=(),
            ordering_violations=ordering_violations,
            missing_stabilization_nodes=(),
        )

    missing_stabilization_nodes = tuple(
        sorted(
            policy.stabilization_nodes - evidence.completed_nodes,
            key=lambda item: item.value,
        )
    )
    if missing_stabilization_nodes:
        return ExecutionTopologyDecision(
            allowed=False,
            reason=ExecutionTopologyReason.STABILIZATION_REQUIRED,
            missing_nodes=(),
            forbidden_nodes=(),
            ordering_violations=(),
            missing_stabilization_nodes=missing_stabilization_nodes,
        )

    if (
        policy.requires_protection_continuity
        and not evidence.protection_continuity_proven
    ):
        return ExecutionTopologyDecision(
            allowed=False,
            reason=ExecutionTopologyReason.PROTECTION_CONTINUITY_REQUIRED,
            missing_nodes=(),
            forbidden_nodes=(),
            ordering_violations=(),
            missing_stabilization_nodes=(),
        )

    return ExecutionTopologyDecision(
        allowed=True,
        reason=ExecutionTopologyReason.ALLOWED,
        missing_nodes=(),
        forbidden_nodes=(),
        ordering_violations=(),
        missing_stabilization_nodes=(),
    )
