from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Tuple


class OrchestrationStep(str, Enum):
    NOOP = "NOOP"
    VALIDATE_LIFECYCLE = "VALIDATE_LIFECYCLE"
    VALIDATE_AUTHORIZATION = "VALIDATE_AUTHORIZATION"
    VALIDATE_AUTHORITY = "VALIDATE_AUTHORITY"
    VALIDATE_CAPABILITY = "VALIDATE_CAPABILITY"
    VALIDATE_ISOLATION = "VALIDATE_ISOLATION"
    VALIDATE_CONFLICTS = "VALIDATE_CONFLICTS"
    VALIDATE_TOPOLOGY = "VALIDATE_TOPOLOGY"
    VALIDATE_CONVERGENCE = "VALIDATE_CONVERGENCE"
    SELECT_RESOLUTION = "SELECT_RESOLUTION"
    VALIDATE_FINALITY = "VALIDATE_FINALITY"
    VALIDATE_RECOVERY = "VALIDATE_RECOVERY"
    VALIDATE_RETRY = "VALIDATE_RETRY"
    VALIDATE_RECONCILIATION = "VALIDATE_RECONCILIATION"
    VALIDATE_CONSISTENCY = "VALIDATE_CONSISTENCY"
    RECORD_AUDIT_TRACE = "RECORD_AUDIT_TRACE"


class OrchestrationBoundary(str, Enum):
    SEMANTIC_ONLY = "SEMANTIC_ONLY"
    PRE_EXECUTION = "PRE_EXECUTION"
    FINALITY_BOUNDARY = "FINALITY_BOUNDARY"
    RECOVERY_BOUNDARY = "RECOVERY_BOUNDARY"
    RETRY_BOUNDARY = "RETRY_BOUNDARY"
    RECONCILIATION_BOUNDARY = "RECONCILIATION_BOUNDARY"
    AUDIT_BOUNDARY = "AUDIT_BOUNDARY"


class OrchestrationSignal(str, Enum):
    ORDERING_PROVEN = "ORDERING_PROVEN"
    DEPENDENCIES_PROVEN = "DEPENDENCIES_PROVEN"
    CONSISTENCY_PROVEN = "CONSISTENCY_PROVEN"
    REPLAY_DETERMINISM_PROVEN = "REPLAY_DETERMINISM_PROVEN"
    PROTECTION_CONTINUITY_PROVEN = "PROTECTION_CONTINUITY_PROVEN"
    AUDIT_TRACE_READY = "AUDIT_TRACE_READY"


class OrchestrationGovernanceReason(str, Enum):
    ALLOWED = "ALLOWED"
    CONSISTENCY_GOVERNANCE_NOT_ALLOWED = "CONSISTENCY_GOVERNANCE_NOT_ALLOWED"
    MISSING_REQUIRED_STEP = "MISSING_REQUIRED_STEP"
    FORBIDDEN_STEP_PRESENT = "FORBIDDEN_STEP_PRESENT"
    MISSING_REQUIRED_SIGNAL = "MISSING_REQUIRED_SIGNAL"
    FORBIDDEN_BOUNDARY = "FORBIDDEN_BOUNDARY"
    STEP_ORDERING_VIOLATION = "STEP_ORDERING_VIOLATION"
    STEP_DEPENDENCY_VIOLATION = "STEP_DEPENDENCY_VIOLATION"
    ORCHESTRATION_CLOSURE_REQUIRED = "ORCHESTRATION_CLOSURE_REQUIRED"
    PROTECTION_CONTINUITY_REQUIRED = "PROTECTION_CONTINUITY_REQUIRED"
    REPLAY_DETERMINISM_REQUIRED = "REPLAY_DETERMINISM_REQUIRED"


@dataclass(frozen=True)
class OrchestrationOrderingRule:
    before: OrchestrationStep
    after: OrchestrationStep


@dataclass(frozen=True)
class OrchestrationStepDependency:
    required_step: OrchestrationStep
    dependent_step: OrchestrationStep


@dataclass(frozen=True)
class SemanticOrchestrationPolicy:
    required_steps: FrozenSet[OrchestrationStep]
    forbidden_steps: FrozenSet[OrchestrationStep]
    allowed_boundaries: FrozenSet[OrchestrationBoundary]
    forbidden_boundaries: FrozenSet[OrchestrationBoundary]
    required_signals: FrozenSet[OrchestrationSignal]
    ordering_rules: FrozenSet[OrchestrationOrderingRule]
    step_dependencies: FrozenSet[OrchestrationStepDependency]
    closure_required: bool = True
    requires_protection_continuity: bool = True
    requires_replay_determinism: bool = True


@dataclass(frozen=True)
class SemanticOrchestrationEvidence:
    completed_steps: FrozenSet[OrchestrationStep]
    requested_steps: FrozenSet[OrchestrationStep]
    requested_boundary: OrchestrationBoundary
    active_signals: FrozenSet[OrchestrationSignal]
    orchestration_closure_proven: bool
    protection_continuity_proven: bool
    replay_determinism_proven: bool


@dataclass(frozen=True)
class SemanticOrchestrationDecision:
    allowed: bool
    reason: OrchestrationGovernanceReason
    missing_steps: Tuple[OrchestrationStep, ...]
    forbidden_steps: Tuple[OrchestrationStep, ...]
    missing_signals: Tuple[OrchestrationSignal, ...]
    forbidden_boundaries: Tuple[OrchestrationBoundary, ...]
    ordering_violations: Tuple[OrchestrationOrderingRule, ...]
    dependency_violations: Tuple[OrchestrationStepDependency, ...]


def evaluate_semantic_orchestration_governance(
    *,
    consistency_governance_allowed: bool,
    policy: SemanticOrchestrationPolicy,
    evidence: SemanticOrchestrationEvidence,
) -> SemanticOrchestrationDecision:
    """
    Pure deterministic semantic orchestration governance evaluator.

    This function does not orchestrate runtime execution.
    It does not schedule tasks, use asyncio, call broker APIs, call Binance APIs,
    inspect websocket state, inspect DB state, use time, IO, randomness, or locks.

    It only decides whether semantic orchestration ordering is admissible.
    """

    if not consistency_governance_allowed:
        return SemanticOrchestrationDecision(
            allowed=False,
            reason=OrchestrationGovernanceReason.CONSISTENCY_GOVERNANCE_NOT_ALLOWED,
            missing_steps=(),
            forbidden_steps=(),
            missing_signals=(),
            forbidden_boundaries=(),
            ordering_violations=(),
            dependency_violations=(),
        )

    available_steps = evidence.completed_steps | evidence.requested_steps

    missing_steps = tuple(
        sorted(
            policy.required_steps - available_steps,
            key=lambda item: item.value,
        )
    )
    if missing_steps:
        return SemanticOrchestrationDecision(
            allowed=False,
            reason=OrchestrationGovernanceReason.MISSING_REQUIRED_STEP,
            missing_steps=missing_steps,
            forbidden_steps=(),
            missing_signals=(),
            forbidden_boundaries=(),
            ordering_violations=(),
            dependency_violations=(),
        )

    forbidden_steps = tuple(
        sorted(
            available_steps & policy.forbidden_steps,
            key=lambda item: item.value,
        )
    )
    if forbidden_steps:
        return SemanticOrchestrationDecision(
            allowed=False,
            reason=OrchestrationGovernanceReason.FORBIDDEN_STEP_PRESENT,
            missing_steps=(),
            forbidden_steps=forbidden_steps,
            missing_signals=(),
            forbidden_boundaries=(),
            ordering_violations=(),
            dependency_violations=(),
        )

    if evidence.requested_boundary in policy.forbidden_boundaries:
        return SemanticOrchestrationDecision(
            allowed=False,
            reason=OrchestrationGovernanceReason.FORBIDDEN_BOUNDARY,
            missing_steps=(),
            forbidden_steps=(),
            missing_signals=(),
            forbidden_boundaries=(evidence.requested_boundary,),
            ordering_violations=(),
            dependency_violations=(),
        )

    if evidence.requested_boundary not in policy.allowed_boundaries:
        return SemanticOrchestrationDecision(
            allowed=False,
            reason=OrchestrationGovernanceReason.FORBIDDEN_BOUNDARY,
            missing_steps=(),
            forbidden_steps=(),
            missing_signals=(),
            forbidden_boundaries=(evidence.requested_boundary,),
            ordering_violations=(),
            dependency_violations=(),
        )

    missing_signals = tuple(
        sorted(
            policy.required_signals - evidence.active_signals,
            key=lambda item: item.value,
        )
    )
    if missing_signals:
        return SemanticOrchestrationDecision(
            allowed=False,
            reason=OrchestrationGovernanceReason.MISSING_REQUIRED_SIGNAL,
            missing_steps=(),
            forbidden_steps=(),
            missing_signals=missing_signals,
            forbidden_boundaries=(),
            ordering_violations=(),
            dependency_violations=(),
        )

    ordering_violations = tuple(
        sorted(
            (
                rule
                for rule in policy.ordering_rules
                if rule.after in evidence.requested_steps
                and rule.before not in evidence.completed_steps
            ),
            key=lambda item: (item.before.value, item.after.value),
        )
    )
    if ordering_violations:
        return SemanticOrchestrationDecision(
            allowed=False,
            reason=OrchestrationGovernanceReason.STEP_ORDERING_VIOLATION,
            missing_steps=(),
            forbidden_steps=(),
            missing_signals=(),
            forbidden_boundaries=(),
            ordering_violations=ordering_violations,
            dependency_violations=(),
        )

    dependency_violations = tuple(
        sorted(
            (
                dependency
                for dependency in policy.step_dependencies
                if dependency.dependent_step in available_steps
                and dependency.required_step not in available_steps
            ),
            key=lambda item: (
                item.required_step.value,
                item.dependent_step.value,
            ),
        )
    )
    if dependency_violations:
        return SemanticOrchestrationDecision(
            allowed=False,
            reason=OrchestrationGovernanceReason.STEP_DEPENDENCY_VIOLATION,
            missing_steps=(),
            forbidden_steps=(),
            missing_signals=(),
            forbidden_boundaries=(),
            ordering_violations=(),
            dependency_violations=dependency_violations,
        )

    if policy.closure_required and not evidence.orchestration_closure_proven:
        return SemanticOrchestrationDecision(
            allowed=False,
            reason=OrchestrationGovernanceReason.ORCHESTRATION_CLOSURE_REQUIRED,
            missing_steps=(),
            forbidden_steps=(),
            missing_signals=(),
            forbidden_boundaries=(),
            ordering_violations=(),
            dependency_violations=(),
        )

    if (
        policy.requires_protection_continuity
        and not evidence.protection_continuity_proven
    ):
        return SemanticOrchestrationDecision(
            allowed=False,
            reason=OrchestrationGovernanceReason.PROTECTION_CONTINUITY_REQUIRED,
            missing_steps=(),
            forbidden_steps=(),
            missing_signals=(),
            forbidden_boundaries=(),
            ordering_violations=(),
            dependency_violations=(),
        )

    if policy.requires_replay_determinism and not evidence.replay_determinism_proven:
        return SemanticOrchestrationDecision(
            allowed=False,
            reason=OrchestrationGovernanceReason.REPLAY_DETERMINISM_REQUIRED,
            missing_steps=(),
            forbidden_steps=(),
            missing_signals=(),
            forbidden_boundaries=(),
            ordering_violations=(),
            dependency_violations=(),
        )

    return SemanticOrchestrationDecision(
        allowed=True,
        reason=OrchestrationGovernanceReason.ALLOWED,
        missing_steps=(),
        forbidden_steps=(),
        missing_signals=(),
        forbidden_boundaries=(),
        ordering_violations=(),
        dependency_violations=(),
    )
