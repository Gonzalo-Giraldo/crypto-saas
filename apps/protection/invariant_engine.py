from dataclasses import dataclass

from apps.protection.constants import (
    REASON_INVALID_CURRENT_STATE,
    REASON_PROTECTION_NOT_VERIFIABLE,
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_ACTIVE,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_STALE_PROVISIONAL_PRESENT,
    STATE_TRAILING_READY,
)
from apps.protection.evidence_snapshot import ProtectionEvidenceSnapshot
from apps.protection.transition_policy import (
    TransitionPolicyResult,
)


@dataclass(frozen=True)
class InvariantResult:
    invariant_name: str
    valid: bool
    reason: str


@dataclass(frozen=True)
class LifecycleInvariantEvaluation:
    allowed: bool
    invariant_results: tuple[InvariantResult, ...]
    policy_result: TransitionPolicyResult


def evaluate_lifecycle_invariants(
    *,
    snapshot: ProtectionEvidenceSnapshot,
    policy_result: TransitionPolicyResult,
) -> LifecycleInvariantEvaluation:
    invariant_results: list[InvariantResult] = []

    invariant_results.append(
        InvariantResult(
            invariant_name="policy_transition_authorized",
            valid=policy_result.allowed,
            reason=policy_result.reason,
        )
    )

    protected_states = {
        STATE_PROVISIONAL_ACTIVE,
        STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
        STATE_PROVISIONAL_CLEANUP_PENDING,
        STATE_STALE_PROVISIONAL_PRESENT,
        STATE_AUTHORITATIVE_ACTIVE,
        STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
        STATE_TRAILING_READY,
    }

    invariant_results.append(
        InvariantResult(
            invariant_name="never_unprotected",
            valid=snapshot.current_state in protected_states,
            reason=(
                policy_result.reason
                if snapshot.current_state not in protected_states
                else "REASON_OK"
            ),
        )
    )

    if (
        snapshot.current_state
        == STATE_PROVISIONAL_CLEANUP_PENDING
    ):
        cleanup_failure_preserves_protection = (
            snapshot.stale_provisional_present
            or snapshot.cleanup_successful
        )

        invariant_results.append(
            InvariantResult(
                invariant_name="cleanup_failure_preserves_protection",
                valid=cleanup_failure_preserves_protection,
                reason=(
                    "REASON_OK"
                    if cleanup_failure_preserves_protection
                    else REASON_PROTECTION_NOT_VERIFIABLE
                ),
            )
        )

    if snapshot.current_state in {
        STATE_AUTHORITATIVE_ACTIVE,
        STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    }:
        trailing_requires_stable_baseline = (
            snapshot.baseline_stable
        )

        invariant_results.append(
            InvariantResult(
                invariant_name="trailing_requires_stable_baseline",
                valid=trailing_requires_stable_baseline,
                reason=(
                    "REASON_OK"
                    if trailing_requires_stable_baseline
                    else REASON_INVALID_CURRENT_STATE
                ),
            )
        )

    if snapshot.current_state == STATE_PROVISIONAL_ACTIVE:
        replacement_requires_reconciliation = (
            snapshot.reconciliation_status == "matched"
        )

        invariant_results.append(
            InvariantResult(
                invariant_name="replacement_requires_reconciliation",
                valid=replacement_requires_reconciliation,
                reason=(
                    "REASON_OK"
                    if replacement_requires_reconciliation
                    else REASON_PROTECTION_NOT_VERIFIABLE
                ),
            )
        )

    allowed = all(
        result.valid
        for result in invariant_results
    )

    return LifecycleInvariantEvaluation(
        allowed=allowed,
        invariant_results=tuple(invariant_results),
        policy_result=policy_result,
    )
