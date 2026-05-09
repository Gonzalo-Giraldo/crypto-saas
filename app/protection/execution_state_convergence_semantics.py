from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Tuple


class ConvergenceState(str, Enum):
    PROVISIONAL_PRESENT = "PROVISIONAL_PRESENT"
    AUTHORITATIVE_CREATED = "AUTHORITATIVE_CREATED"
    AUTHORITATIVE_VERIFIED = "AUTHORITATIVE_VERIFIED"
    REPLACEMENT_PENDING = "REPLACEMENT_PENDING"
    REPLACEMENT_RECONCILED = "REPLACEMENT_RECONCILED"
    CLEANUP_PENDING = "CLEANUP_PENDING"
    CLEANUP_CONFIRMED = "CLEANUP_CONFIRMED"
    STABLE_BASELINE_ESTABLISHED = "STABLE_BASELINE_ESTABLISHED"
    TRAILING_ACTIVE = "TRAILING_ACTIVE"
    AUDIT_TRACE_COMPLETE = "AUDIT_TRACE_COMPLETE"


class ConvergenceReason(str, Enum):
    ALLOWED = "ALLOWED"
    TOPOLOGY_SEMANTICS_NOT_ALLOWED = "TOPOLOGY_SEMANTICS_NOT_ALLOWED"
    MISSING_REQUIRED_CONVERGENCE_STATE = (
        "MISSING_REQUIRED_CONVERGENCE_STATE"
    )
    FORBIDDEN_CONVERGENCE_STATE = "FORBIDDEN_CONVERGENCE_STATE"
    UNRESOLVED_CONVERGENCE_STATE = "UNRESOLVED_CONVERGENCE_STATE"
    AUTHORITATIVE_CONVERGENCE_REQUIRED = (
        "AUTHORITATIVE_CONVERGENCE_REQUIRED"
    )
    STABLE_BASELINE_REQUIRED = "STABLE_BASELINE_REQUIRED"
    PROTECTION_CONTINUITY_REQUIRED = (
        "PROTECTION_CONTINUITY_REQUIRED"
    )


@dataclass(frozen=True)
class ConvergenceDependencyRule:
    required_state: ConvergenceState
    dependent_state: ConvergenceState


@dataclass(frozen=True)
class ExecutionStateConvergencePolicy:
    required_states: FrozenSet[ConvergenceState]
    forbidden_states: FrozenSet[ConvergenceState]
    unresolved_states: FrozenSet[ConvergenceState]
    dependency_rules: FrozenSet[ConvergenceDependencyRule]
    authoritative_states: FrozenSet[ConvergenceState]
    stable_baseline_states: FrozenSet[ConvergenceState]
    requires_protection_continuity: bool = True


@dataclass(frozen=True)
class ExecutionStateConvergenceEvidence:
    active_states: FrozenSet[ConvergenceState]
    requested_states: FrozenSet[ConvergenceState]
    protection_continuity_proven: bool


@dataclass(frozen=True)
class ExecutionStateConvergenceDecision:
    allowed: bool
    reason: ConvergenceReason
    missing_required_states: Tuple[ConvergenceState, ...]
    forbidden_states: Tuple[ConvergenceState, ...]
    unresolved_states: Tuple[ConvergenceState, ...]
    dependency_violations: Tuple[ConvergenceDependencyRule, ...]
    missing_authoritative_states: Tuple[ConvergenceState, ...]
    missing_stable_baseline_states: Tuple[ConvergenceState, ...]


def evaluate_execution_state_convergence_semantics(
    *,
    topology_semantics_allowed: bool,
    policy: ExecutionStateConvergencePolicy,
    evidence: ExecutionStateConvergenceEvidence,
) -> ExecutionStateConvergenceDecision:
    """
    Pure deterministic execution state convergence evaluator.

    This function does not execute, orchestrate, retry, persist, lock,
    inspect runtime state, inspect exchange state, inspect broker state,
    inspect websocket state, use time, IO, or async orchestration.

    It only validates semantic lifecycle convergence legality.
    """

    if not topology_semantics_allowed:
        return ExecutionStateConvergenceDecision(
            allowed=False,
            reason=ConvergenceReason.TOPOLOGY_SEMANTICS_NOT_ALLOWED,
            missing_required_states=(),
            forbidden_states=(),
            unresolved_states=(),
            dependency_violations=(),
            missing_authoritative_states=(),
            missing_stable_baseline_states=(),
        )

    available_states = (
        evidence.active_states |
        evidence.requested_states
    )

    missing_required_states = tuple(
        sorted(
            policy.required_states - available_states,
            key=lambda item: item.value,
        )
    )
    if missing_required_states:
        return ExecutionStateConvergenceDecision(
            allowed=False,
            reason=ConvergenceReason.MISSING_REQUIRED_CONVERGENCE_STATE,
            missing_required_states=missing_required_states,
            forbidden_states=(),
            unresolved_states=(),
            dependency_violations=(),
            missing_authoritative_states=(),
            missing_stable_baseline_states=(),
        )

    forbidden_states = tuple(
        sorted(
            available_states & policy.forbidden_states,
            key=lambda item: item.value,
        )
    )
    if forbidden_states:
        return ExecutionStateConvergenceDecision(
            allowed=False,
            reason=ConvergenceReason.FORBIDDEN_CONVERGENCE_STATE,
            missing_required_states=(),
            forbidden_states=forbidden_states,
            unresolved_states=(),
            dependency_violations=(),
            missing_authoritative_states=(),
            missing_stable_baseline_states=(),
        )

    unresolved_states = tuple(
        sorted(
            available_states & policy.unresolved_states,
            key=lambda item: item.value,
        )
    )
    if unresolved_states:
        return ExecutionStateConvergenceDecision(
            allowed=False,
            reason=ConvergenceReason.UNRESOLVED_CONVERGENCE_STATE,
            missing_required_states=(),
            forbidden_states=(),
            unresolved_states=unresolved_states,
            dependency_violations=(),
            missing_authoritative_states=(),
            missing_stable_baseline_states=(),
        )

    dependency_violations = tuple(
        sorted(
            (
                rule
                for rule in policy.dependency_rules
                if rule.dependent_state in evidence.requested_states
                and rule.required_state not in evidence.active_states
            ),
            key=lambda item: (
                item.required_state.value,
                item.dependent_state.value,
            ),
        )
    )
    if dependency_violations:
        return ExecutionStateConvergenceDecision(
            allowed=False,
            reason=ConvergenceReason.UNRESOLVED_CONVERGENCE_STATE,
            missing_required_states=(),
            forbidden_states=(),
            unresolved_states=(),
            dependency_violations=dependency_violations,
            missing_authoritative_states=(),
            missing_stable_baseline_states=(),
        )

    missing_authoritative_states = tuple(
        sorted(
            policy.authoritative_states - evidence.active_states,
            key=lambda item: item.value,
        )
    )
    if missing_authoritative_states:
        return ExecutionStateConvergenceDecision(
            allowed=False,
            reason=ConvergenceReason.AUTHORITATIVE_CONVERGENCE_REQUIRED,
            missing_required_states=(),
            forbidden_states=(),
            unresolved_states=(),
            dependency_violations=(),
            missing_authoritative_states=missing_authoritative_states,
            missing_stable_baseline_states=(),
        )

    missing_stable_baseline_states = tuple(
        sorted(
            policy.stable_baseline_states - evidence.active_states,
            key=lambda item: item.value,
        )
    )
    if missing_stable_baseline_states:
        return ExecutionStateConvergenceDecision(
            allowed=False,
            reason=ConvergenceReason.STABLE_BASELINE_REQUIRED,
            missing_required_states=(),
            forbidden_states=(),
            unresolved_states=(),
            dependency_violations=(),
            missing_authoritative_states=(),
            missing_stable_baseline_states=missing_stable_baseline_states,
        )

    if (
        policy.requires_protection_continuity
        and not evidence.protection_continuity_proven
    ):
        return ExecutionStateConvergenceDecision(
            allowed=False,
            reason=ConvergenceReason.PROTECTION_CONTINUITY_REQUIRED,
            missing_required_states=(),
            forbidden_states=(),
            unresolved_states=(),
            dependency_violations=(),
            missing_authoritative_states=(),
            missing_stable_baseline_states=(),
        )

    return ExecutionStateConvergenceDecision(
        allowed=True,
        reason=ConvergenceReason.ALLOWED,
        missing_required_states=(),
        forbidden_states=(),
        unresolved_states=(),
        dependency_violations=(),
        missing_authoritative_states=(),
        missing_stable_baseline_states=(),
    )
