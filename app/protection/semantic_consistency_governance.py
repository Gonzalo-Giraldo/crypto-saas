from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Tuple


class ConsistencyLayer(str, Enum):
    LIFECYCLE = "LIFECYCLE"
    AUTHORIZATION = "AUTHORIZATION"
    AUTHORITY = "AUTHORITY"
    CAPABILITY = "CAPABILITY"
    ISOLATION = "ISOLATION"
    CONFLICT = "CONFLICT"
    TOPOLOGY = "TOPOLOGY"
    CONVERGENCE = "CONVERGENCE"
    RESOLUTION = "RESOLUTION"
    FINALITY = "FINALITY"
    RECOVERY = "RECOVERY"
    RETRY = "RETRY"
    RECONCILIATION = "RECONCILIATION"
    AUDIT = "AUDIT"


class ConsistencySignal(str, Enum):
    PROTECTION_CONTINUITY_PROVEN = "PROTECTION_CONTINUITY_PROVEN"
    REPLAY_DETERMINISM_PROVEN = "REPLAY_DETERMINISM_PROVEN"
    AUTHORITATIVE_VERIFIED = "AUTHORITATIVE_VERIFIED"
    STABLE_BASELINE_CONFIRMED = "STABLE_BASELINE_CONFIRMED"
    FINALITY_CONFIRMED = "FINALITY_CONFIRMED"
    RECOVERY_ADMISSIBLE = "RECOVERY_ADMISSIBLE"
    RETRY_ADMISSIBLE = "RETRY_ADMISSIBLE"
    RECONCILIATION_CLOSED = "RECONCILIATION_CLOSED"
    AUDIT_TRACE_PRESENT = "AUDIT_TRACE_PRESENT"


class ConsistencyContradiction(str, Enum):
    FINALITY_WITH_UNRESOLVED_CONVERGENCE = (
        "FINALITY_WITH_UNRESOLVED_CONVERGENCE"
    )
    RETRY_AFTER_FINALITY = "RETRY_AFTER_FINALITY"
    RECOVERY_WITHOUT_REPLAY_DETERMINISM = (
        "RECOVERY_WITHOUT_REPLAY_DETERMINISM"
    )
    RECONCILIATION_WITHOUT_CLOSURE = (
        "RECONCILIATION_WITHOUT_CLOSURE"
    )
    TRAILING_WITHOUT_STABLE_BASELINE = (
        "TRAILING_WITHOUT_STABLE_BASELINE"
    )
    AUTHORITY_WITHOUT_CAPABILITY = "AUTHORITY_WITHOUT_CAPABILITY"
    CAPABILITY_WITHOUT_ISOLATION = "CAPABILITY_WITHOUT_ISOLATION"
    EXECUTION_WITHOUT_PROTECTION_CONTINUITY = (
        "EXECUTION_WITHOUT_PROTECTION_CONTINUITY"
    )


class ConsistencyGovernanceReason(str, Enum):
    ALLOWED = "ALLOWED"
    RECONCILIATION_GOVERNANCE_NOT_ALLOWED = (
        "RECONCILIATION_GOVERNANCE_NOT_ALLOWED"
    )
    MISSING_REQUIRED_LAYER = "MISSING_REQUIRED_LAYER"
    MISSING_REQUIRED_SIGNAL = "MISSING_REQUIRED_SIGNAL"
    FORBIDDEN_LAYER_PRESENT = "FORBIDDEN_LAYER_PRESENT"
    FORBIDDEN_SIGNAL_PRESENT = "FORBIDDEN_SIGNAL_PRESENT"
    SEMANTIC_CONTRADICTION = "SEMANTIC_CONTRADICTION"
    LAYER_DEPENDENCY_VIOLATION = "LAYER_DEPENDENCY_VIOLATION"
    PROTECTION_CONTINUITY_REQUIRED = (
        "PROTECTION_CONTINUITY_REQUIRED"
    )
    REPLAY_DETERMINISM_REQUIRED = (
        "REPLAY_DETERMINISM_REQUIRED"
    )


@dataclass(frozen=True)
class ConsistencyLayerDependency:
    required_layer: ConsistencyLayer
    dependent_layer: ConsistencyLayer


@dataclass(frozen=True)
class SemanticConsistencyPolicy:
    required_layers: FrozenSet[ConsistencyLayer]
    forbidden_layers: FrozenSet[ConsistencyLayer]
    required_signals: FrozenSet[ConsistencySignal]
    forbidden_signals: FrozenSet[ConsistencySignal]
    forbidden_contradictions: FrozenSet[ConsistencyContradiction]
    layer_dependencies: FrozenSet[ConsistencyLayerDependency]
    requires_protection_continuity: bool = True
    requires_replay_determinism: bool = True


@dataclass(frozen=True)
class SemanticConsistencyEvidence:
    active_layers: FrozenSet[ConsistencyLayer]
    active_signals: FrozenSet[ConsistencySignal]
    observed_contradictions: FrozenSet[ConsistencyContradiction]
    protection_continuity_proven: bool
    replay_determinism_proven: bool


@dataclass(frozen=True)
class SemanticConsistencyDecision:
    allowed: bool
    reason: ConsistencyGovernanceReason
    missing_layers: Tuple[ConsistencyLayer, ...]
    missing_signals: Tuple[ConsistencySignal, ...]
    forbidden_layers: Tuple[ConsistencyLayer, ...]
    forbidden_signals: Tuple[ConsistencySignal, ...]
    contradictions: Tuple[ConsistencyContradiction, ...]
    layer_dependency_violations: Tuple[ConsistencyLayerDependency, ...]


def evaluate_semantic_consistency_governance(
    *,
    reconciliation_governance_allowed: bool,
    policy: SemanticConsistencyPolicy,
    evidence: SemanticConsistencyEvidence,
) -> SemanticConsistencyDecision:
    """
    Pure deterministic semantic consistency governance evaluator.

    This function does not orchestrate runtime state.
    It does not inspect websocket state, call broker APIs,
    call Binance APIs, inspect DB state, use time, IO,
    randomness, or async orchestration.

    It only decides whether cross-layer semantic consistency is admissible.
    """

    if not reconciliation_governance_allowed:
        return SemanticConsistencyDecision(
            allowed=False,
            reason=ConsistencyGovernanceReason.RECONCILIATION_GOVERNANCE_NOT_ALLOWED,
            missing_layers=(),
            missing_signals=(),
            forbidden_layers=(),
            forbidden_signals=(),
            contradictions=(),
            layer_dependency_violations=(),
        )

    missing_layers = tuple(
        sorted(
            policy.required_layers - evidence.active_layers,
            key=lambda item: item.value,
        )
    )
    if missing_layers:
        return SemanticConsistencyDecision(
            allowed=False,
            reason=ConsistencyGovernanceReason.MISSING_REQUIRED_LAYER,
            missing_layers=missing_layers,
            missing_signals=(),
            forbidden_layers=(),
            forbidden_signals=(),
            contradictions=(),
            layer_dependency_violations=(),
        )

    missing_signals = tuple(
        sorted(
            policy.required_signals - evidence.active_signals,
            key=lambda item: item.value,
        )
    )
    if missing_signals:
        return SemanticConsistencyDecision(
            allowed=False,
            reason=ConsistencyGovernanceReason.MISSING_REQUIRED_SIGNAL,
            missing_layers=(),
            missing_signals=missing_signals,
            forbidden_layers=(),
            forbidden_signals=(),
            contradictions=(),
            layer_dependency_violations=(),
        )

    forbidden_layers = tuple(
        sorted(
            evidence.active_layers & policy.forbidden_layers,
            key=lambda item: item.value,
        )
    )
    if forbidden_layers:
        return SemanticConsistencyDecision(
            allowed=False,
            reason=ConsistencyGovernanceReason.FORBIDDEN_LAYER_PRESENT,
            missing_layers=(),
            missing_signals=(),
            forbidden_layers=forbidden_layers,
            forbidden_signals=(),
            contradictions=(),
            layer_dependency_violations=(),
        )

    forbidden_signals = tuple(
        sorted(
            evidence.active_signals & policy.forbidden_signals,
            key=lambda item: item.value,
        )
    )
    if forbidden_signals:
        return SemanticConsistencyDecision(
            allowed=False,
            reason=ConsistencyGovernanceReason.FORBIDDEN_SIGNAL_PRESENT,
            missing_layers=(),
            missing_signals=(),
            forbidden_layers=(),
            forbidden_signals=forbidden_signals,
            contradictions=(),
            layer_dependency_violations=(),
        )

    contradictions = tuple(
        sorted(
            evidence.observed_contradictions
            & policy.forbidden_contradictions,
            key=lambda item: item.value,
        )
    )
    if contradictions:
        return SemanticConsistencyDecision(
            allowed=False,
            reason=ConsistencyGovernanceReason.SEMANTIC_CONTRADICTION,
            missing_layers=(),
            missing_signals=(),
            forbidden_layers=(),
            forbidden_signals=(),
            contradictions=contradictions,
            layer_dependency_violations=(),
        )

    layer_dependency_violations = tuple(
        sorted(
            (
                dependency
                for dependency in policy.layer_dependencies
                if dependency.dependent_layer in evidence.active_layers
                and dependency.required_layer not in evidence.active_layers
            ),
            key=lambda item: (
                item.required_layer.value,
                item.dependent_layer.value,
            ),
        )
    )
    if layer_dependency_violations:
        return SemanticConsistencyDecision(
            allowed=False,
            reason=ConsistencyGovernanceReason.LAYER_DEPENDENCY_VIOLATION,
            missing_layers=(),
            missing_signals=(),
            forbidden_layers=(),
            forbidden_signals=(),
            contradictions=(),
            layer_dependency_violations=layer_dependency_violations,
        )

    if (
        policy.requires_protection_continuity
        and not evidence.protection_continuity_proven
    ):
        return SemanticConsistencyDecision(
            allowed=False,
            reason=ConsistencyGovernanceReason.PROTECTION_CONTINUITY_REQUIRED,
            missing_layers=(),
            missing_signals=(),
            forbidden_layers=(),
            forbidden_signals=(),
            contradictions=(),
            layer_dependency_violations=(),
        )

    if (
        policy.requires_replay_determinism
        and not evidence.replay_determinism_proven
    ):
        return SemanticConsistencyDecision(
            allowed=False,
            reason=ConsistencyGovernanceReason.REPLAY_DETERMINISM_REQUIRED,
            missing_layers=(),
            missing_signals=(),
            forbidden_layers=(),
            forbidden_signals=(),
            contradictions=(),
            layer_dependency_violations=(),
        )

    return SemanticConsistencyDecision(
        allowed=True,
        reason=ConsistencyGovernanceReason.ALLOWED,
        missing_layers=(),
        missing_signals=(),
        forbidden_layers=(),
        forbidden_signals=(),
        contradictions=(),
        layer_dependency_violations=(),
    )
