from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Tuple


class ExecutionPlanIntent(str, Enum):
    NOOP = "NOOP"
    PLAN_AUTHORITATIVE_CREATION = "PLAN_AUTHORITATIVE_CREATION"
    PLAN_AUTHORITATIVE_REPLACEMENT = "PLAN_AUTHORITATIVE_REPLACEMENT"
    PLAN_PROVISIONAL_CLEANUP = "PLAN_PROVISIONAL_CLEANUP"
    PLAN_TRAILING_ACTIVATION = "PLAN_TRAILING_ACTIVATION"
    PLAN_RECONCILIATION_ONLY = "PLAN_RECONCILIATION_ONLY"
    PLAN_AUDIT_ONLY = "PLAN_AUDIT_ONLY"


class ExecutionPlanScope(str, Enum):
    SEMANTIC_ONLY = "SEMANTIC_ONLY"
    AUTHORITATIVE_SCOPE = "AUTHORITATIVE_SCOPE"
    PROVISIONAL_SCOPE = "PROVISIONAL_SCOPE"
    REPLACEMENT_SCOPE = "REPLACEMENT_SCOPE"
    CLEANUP_SCOPE = "CLEANUP_SCOPE"
    TRAILING_SCOPE = "TRAILING_SCOPE"
    RECONCILIATION_SCOPE = "RECONCILIATION_SCOPE"
    AUDIT_SCOPE = "AUDIT_SCOPE"


class ExecutionPlanStep(str, Enum):
    NOOP = "NOOP"
    PLAN_VALIDATE_PRECONDITIONS = "PLAN_VALIDATE_PRECONDITIONS"
    PLAN_VALIDATE_AUTHORIZATION = "PLAN_VALIDATE_AUTHORIZATION"
    PLAN_VALIDATE_AUTHORITY = "PLAN_VALIDATE_AUTHORITY"
    PLAN_VALIDATE_CAPABILITY = "PLAN_VALIDATE_CAPABILITY"
    PLAN_VALIDATE_ISOLATION = "PLAN_VALIDATE_ISOLATION"
    PLAN_VALIDATE_CONFLICTS = "PLAN_VALIDATE_CONFLICTS"
    PLAN_VALIDATE_CONVERGENCE = "PLAN_VALIDATE_CONVERGENCE"
    PLAN_VALIDATE_FINALITY = "PLAN_VALIDATE_FINALITY"
    PLAN_VALIDATE_RETRY = "PLAN_VALIDATE_RETRY"
    PLAN_VALIDATE_RECONCILIATION = "PLAN_VALIDATE_RECONCILIATION"
    PLAN_VALIDATE_ORCHESTRATION = "PLAN_VALIDATE_ORCHESTRATION"
    PLAN_RECORD_AUDIT = "PLAN_RECORD_AUDIT"


class ExecutionPlanningSignal(str, Enum):
    PLAN_TOPOLOGY_PROVEN = "PLAN_TOPOLOGY_PROVEN"
    PLAN_SCOPE_PROVEN = "PLAN_SCOPE_PROVEN"
    PLAN_SEQUENCE_PROVEN = "PLAN_SEQUENCE_PROVEN"
    PLAN_CLOSURE_PROVEN = "PLAN_CLOSURE_PROVEN"
    PROTECTION_CONTINUITY_PROVEN = "PROTECTION_CONTINUITY_PROVEN"
    REPLAY_DETERMINISM_PROVEN = "REPLAY_DETERMINISM_PROVEN"


class ExecutionPlanningGovernanceReason(str, Enum):
    ALLOWED = "ALLOWED"
    ORCHESTRATION_GOVERNANCE_NOT_ALLOWED = "ORCHESTRATION_GOVERNANCE_NOT_ALLOWED"
    FORBIDDEN_PLAN_INTENT = "FORBIDDEN_PLAN_INTENT"
    FORBIDDEN_PLAN_SCOPE = "FORBIDDEN_PLAN_SCOPE"
    INTENT_SCOPE_MISMATCH = "INTENT_SCOPE_MISMATCH"
    MISSING_REQUIRED_PLAN_STEP = "MISSING_REQUIRED_PLAN_STEP"
    FORBIDDEN_PLAN_STEP_PRESENT = "FORBIDDEN_PLAN_STEP_PRESENT"
    PLAN_STEP_ORDERING_VIOLATION = "PLAN_STEP_ORDERING_VIOLATION"
    PLAN_STEP_DEPENDENCY_VIOLATION = "PLAN_STEP_DEPENDENCY_VIOLATION"
    MISSING_REQUIRED_SIGNAL = "MISSING_REQUIRED_SIGNAL"
    PLAN_CLOSURE_REQUIRED = "PLAN_CLOSURE_REQUIRED"
    PROTECTION_CONTINUITY_REQUIRED = "PROTECTION_CONTINUITY_REQUIRED"
    REPLAY_DETERMINISM_REQUIRED = "REPLAY_DETERMINISM_REQUIRED"


@dataclass(frozen=True)
class ExecutionPlanIntentScopeRule:
    intent: ExecutionPlanIntent
    scope: ExecutionPlanScope


@dataclass(frozen=True)
class ExecutionPlanOrderingRule:
    before: ExecutionPlanStep
    after: ExecutionPlanStep


@dataclass(frozen=True)
class ExecutionPlanStepDependency:
    required_step: ExecutionPlanStep
    dependent_step: ExecutionPlanStep


@dataclass(frozen=True)
class SemanticExecutionPlanningPolicy:
    allowed_intents: FrozenSet[ExecutionPlanIntent]
    forbidden_intents: FrozenSet[ExecutionPlanIntent]
    allowed_scopes: FrozenSet[ExecutionPlanScope]
    forbidden_scopes: FrozenSet[ExecutionPlanScope]
    intent_scope_rules: FrozenSet[ExecutionPlanIntentScopeRule]
    required_steps: FrozenSet[ExecutionPlanStep]
    forbidden_steps: FrozenSet[ExecutionPlanStep]
    ordering_rules: FrozenSet[ExecutionPlanOrderingRule]
    step_dependencies: FrozenSet[ExecutionPlanStepDependency]
    required_signals: FrozenSet[ExecutionPlanningSignal]
    plan_closure_required: bool = True
    requires_protection_continuity: bool = True
    requires_replay_determinism: bool = True


@dataclass(frozen=True)
class SemanticExecutionPlanningEvidence:
    requested_intent: ExecutionPlanIntent
    requested_scope: ExecutionPlanScope
    completed_steps: FrozenSet[ExecutionPlanStep]
    requested_steps: FrozenSet[ExecutionPlanStep]
    active_signals: FrozenSet[ExecutionPlanningSignal]
    plan_closure_proven: bool
    protection_continuity_proven: bool
    replay_determinism_proven: bool


@dataclass(frozen=True)
class SemanticExecutionPlanningDecision:
    allowed: bool
    reason: ExecutionPlanningGovernanceReason
    plan_intent: ExecutionPlanIntent | None
    plan_scope: ExecutionPlanScope | None
    forbidden_intents: Tuple[ExecutionPlanIntent, ...]
    forbidden_scopes: Tuple[ExecutionPlanScope, ...]
    intent_scope_violations: Tuple[ExecutionPlanIntentScopeRule, ...]
    missing_steps: Tuple[ExecutionPlanStep, ...]
    forbidden_steps: Tuple[ExecutionPlanStep, ...]
    ordering_violations: Tuple[ExecutionPlanOrderingRule, ...]
    dependency_violations: Tuple[ExecutionPlanStepDependency, ...]
    missing_signals: Tuple[ExecutionPlanningSignal, ...]


def evaluate_semantic_execution_planning_governance(
    *,
    orchestration_governance_allowed: bool,
    policy: SemanticExecutionPlanningPolicy,
    evidence: SemanticExecutionPlanningEvidence,
) -> SemanticExecutionPlanningDecision:
    """
    Pure deterministic semantic execution planning governance evaluator.

    This function does not execute a plan.
    It does not schedule, use asyncio, call broker APIs, call Binance APIs,
    inspect websocket state, inspect DB state, use time, IO, randomness, or locks.

    It only decides whether a semantic execution plan is admissible.
    """

    empty_decision = {
        "forbidden_intents": (),
        "forbidden_scopes": (),
        "intent_scope_violations": (),
        "missing_steps": (),
        "forbidden_steps": (),
        "ordering_violations": (),
        "dependency_violations": (),
        "missing_signals": (),
    }

    if not orchestration_governance_allowed:
        return SemanticExecutionPlanningDecision(
            allowed=False,
            reason=ExecutionPlanningGovernanceReason.ORCHESTRATION_GOVERNANCE_NOT_ALLOWED,
            plan_intent=None,
            plan_scope=None,
            **empty_decision,
        )

    if evidence.requested_intent in policy.forbidden_intents:
        return SemanticExecutionPlanningDecision(
            allowed=False,
            reason=ExecutionPlanningGovernanceReason.FORBIDDEN_PLAN_INTENT,
            plan_intent=None,
            plan_scope=evidence.requested_scope,
            forbidden_intents=(evidence.requested_intent,),
            forbidden_scopes=(),
            intent_scope_violations=(),
            missing_steps=(),
            forbidden_steps=(),
            ordering_violations=(),
            dependency_violations=(),
            missing_signals=(),
        )

    if evidence.requested_intent not in policy.allowed_intents:
        return SemanticExecutionPlanningDecision(
            allowed=False,
            reason=ExecutionPlanningGovernanceReason.FORBIDDEN_PLAN_INTENT,
            plan_intent=None,
            plan_scope=evidence.requested_scope,
            forbidden_intents=(evidence.requested_intent,),
            forbidden_scopes=(),
            intent_scope_violations=(),
            missing_steps=(),
            forbidden_steps=(),
            ordering_violations=(),
            dependency_violations=(),
            missing_signals=(),
        )

    if evidence.requested_scope in policy.forbidden_scopes:
        return SemanticExecutionPlanningDecision(
            allowed=False,
            reason=ExecutionPlanningGovernanceReason.FORBIDDEN_PLAN_SCOPE,
            plan_intent=evidence.requested_intent,
            plan_scope=None,
            forbidden_intents=(),
            forbidden_scopes=(evidence.requested_scope,),
            intent_scope_violations=(),
            missing_steps=(),
            forbidden_steps=(),
            ordering_violations=(),
            dependency_violations=(),
            missing_signals=(),
        )

    if evidence.requested_scope not in policy.allowed_scopes:
        return SemanticExecutionPlanningDecision(
            allowed=False,
            reason=ExecutionPlanningGovernanceReason.FORBIDDEN_PLAN_SCOPE,
            plan_intent=evidence.requested_intent,
            plan_scope=None,
            forbidden_intents=(),
            forbidden_scopes=(evidence.requested_scope,),
            intent_scope_violations=(),
            missing_steps=(),
            forbidden_steps=(),
            ordering_violations=(),
            dependency_violations=(),
            missing_signals=(),
        )

    intent_scope_violations = tuple(
        sorted(
            (
                rule
                for rule in policy.intent_scope_rules
                if rule.intent == evidence.requested_intent
                and rule.scope != evidence.requested_scope
            ),
            key=lambda item: (item.intent.value, item.scope.value),
        )
    )
    if intent_scope_violations:
        return SemanticExecutionPlanningDecision(
            allowed=False,
            reason=ExecutionPlanningGovernanceReason.INTENT_SCOPE_MISMATCH,
            plan_intent=evidence.requested_intent,
            plan_scope=evidence.requested_scope,
            forbidden_intents=(),
            forbidden_scopes=(),
            intent_scope_violations=intent_scope_violations,
            missing_steps=(),
            forbidden_steps=(),
            ordering_violations=(),
            dependency_violations=(),
            missing_signals=(),
        )

    available_steps = evidence.completed_steps | evidence.requested_steps

    missing_steps = tuple(
        sorted(
            policy.required_steps - available_steps,
            key=lambda item: item.value,
        )
    )
    if missing_steps:
        return SemanticExecutionPlanningDecision(
            allowed=False,
            reason=ExecutionPlanningGovernanceReason.MISSING_REQUIRED_PLAN_STEP,
            plan_intent=evidence.requested_intent,
            plan_scope=evidence.requested_scope,
            forbidden_intents=(),
            forbidden_scopes=(),
            intent_scope_violations=(),
            missing_steps=missing_steps,
            forbidden_steps=(),
            ordering_violations=(),
            dependency_violations=(),
            missing_signals=(),
        )

    forbidden_steps = tuple(
        sorted(
            available_steps & policy.forbidden_steps,
            key=lambda item: item.value,
        )
    )
    if forbidden_steps:
        return SemanticExecutionPlanningDecision(
            allowed=False,
            reason=ExecutionPlanningGovernanceReason.FORBIDDEN_PLAN_STEP_PRESENT,
            plan_intent=evidence.requested_intent,
            plan_scope=evidence.requested_scope,
            forbidden_intents=(),
            forbidden_scopes=(),
            intent_scope_violations=(),
            missing_steps=(),
            forbidden_steps=forbidden_steps,
            ordering_violations=(),
            dependency_violations=(),
            missing_signals=(),
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
        return SemanticExecutionPlanningDecision(
            allowed=False,
            reason=ExecutionPlanningGovernanceReason.PLAN_STEP_ORDERING_VIOLATION,
            plan_intent=evidence.requested_intent,
            plan_scope=evidence.requested_scope,
            forbidden_intents=(),
            forbidden_scopes=(),
            intent_scope_violations=(),
            missing_steps=(),
            forbidden_steps=(),
            ordering_violations=ordering_violations,
            dependency_violations=(),
            missing_signals=(),
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
        return SemanticExecutionPlanningDecision(
            allowed=False,
            reason=ExecutionPlanningGovernanceReason.PLAN_STEP_DEPENDENCY_VIOLATION,
            plan_intent=evidence.requested_intent,
            plan_scope=evidence.requested_scope,
            forbidden_intents=(),
            forbidden_scopes=(),
            intent_scope_violations=(),
            missing_steps=(),
            forbidden_steps=(),
            ordering_violations=(),
            dependency_violations=dependency_violations,
            missing_signals=(),
        )

    missing_signals = tuple(
        sorted(
            policy.required_signals - evidence.active_signals,
            key=lambda item: item.value,
        )
    )
    if missing_signals:
        return SemanticExecutionPlanningDecision(
            allowed=False,
            reason=ExecutionPlanningGovernanceReason.MISSING_REQUIRED_SIGNAL,
            plan_intent=evidence.requested_intent,
            plan_scope=evidence.requested_scope,
            forbidden_intents=(),
            forbidden_scopes=(),
            intent_scope_violations=(),
            missing_steps=(),
            forbidden_steps=(),
            ordering_violations=(),
            dependency_violations=(),
            missing_signals=missing_signals,
        )

    if policy.plan_closure_required and not evidence.plan_closure_proven:
        return SemanticExecutionPlanningDecision(
            allowed=False,
            reason=ExecutionPlanningGovernanceReason.PLAN_CLOSURE_REQUIRED,
            plan_intent=evidence.requested_intent,
            plan_scope=evidence.requested_scope,
            forbidden_intents=(),
            forbidden_scopes=(),
            intent_scope_violations=(),
            missing_steps=(),
            forbidden_steps=(),
            ordering_violations=(),
            dependency_violations=(),
            missing_signals=(),
        )

    if (
        policy.requires_protection_continuity
        and not evidence.protection_continuity_proven
    ):
        return SemanticExecutionPlanningDecision(
            allowed=False,
            reason=ExecutionPlanningGovernanceReason.PROTECTION_CONTINUITY_REQUIRED,
            plan_intent=evidence.requested_intent,
            plan_scope=evidence.requested_scope,
            forbidden_intents=(),
            forbidden_scopes=(),
            intent_scope_violations=(),
            missing_steps=(),
            forbidden_steps=(),
            ordering_violations=(),
            dependency_violations=(),
            missing_signals=(),
        )

    if policy.requires_replay_determinism and not evidence.replay_determinism_proven:
        return SemanticExecutionPlanningDecision(
            allowed=False,
            reason=ExecutionPlanningGovernanceReason.REPLAY_DETERMINISM_REQUIRED,
            plan_intent=evidence.requested_intent,
            plan_scope=evidence.requested_scope,
            forbidden_intents=(),
            forbidden_scopes=(),
            intent_scope_violations=(),
            missing_steps=(),
            forbidden_steps=(),
            ordering_violations=(),
            dependency_violations=(),
            missing_signals=(),
        )

    return SemanticExecutionPlanningDecision(
        allowed=True,
        reason=ExecutionPlanningGovernanceReason.ALLOWED,
        plan_intent=evidence.requested_intent,
        plan_scope=evidence.requested_scope,
        forbidden_intents=(),
        forbidden_scopes=(),
        intent_scope_violations=(),
        missing_steps=(),
        forbidden_steps=(),
        ordering_violations=(),
        dependency_violations=(),
        missing_signals=(),
    )
