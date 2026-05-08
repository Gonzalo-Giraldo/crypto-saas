from dataclasses import dataclass

from apps.protection.constants import (
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_STALE_PROVISIONAL_PRESENT,
    STATE_TRAILING_READY,
)
from apps.protection.invariant_engine import LifecycleInvariantEvaluation


ACTION_ACCEPT_AUTHORITATIVE_EQUIVALENT = "ACCEPT_AUTHORITATIVE_EQUIVALENT"
ACTION_START_AUTHORITATIVE_REPLACEMENT = "START_AUTHORITATIVE_REPLACEMENT"
ACTION_START_PROVISIONAL_CLEANUP = "START_PROVISIONAL_CLEANUP"
ACTION_MARK_AUTHORITATIVE_ACTIVE = "MARK_AUTHORITATIVE_ACTIVE"
ACTION_MARK_STALE_PROVISIONAL_PRESENT = "MARK_STALE_PROVISIONAL_PRESENT"
ACTION_RETRY_PROVISIONAL_CLEANUP = "RETRY_PROVISIONAL_CLEANUP"
ACTION_ACTIVATE_TRAILING = "ACTIVATE_TRAILING"
ACTION_NONE = "NO_RUNTIME_ACTION"


@dataclass(frozen=True)
class ProtectionRuntimeContract:
    allowed: bool
    current_state: str
    next_state: str | None
    required_action: str
    requires_authoritative_confirmation: bool
    requires_cleanup_confirmation: bool
    requires_trailing_confirmation: bool
    reason: str


def build_runtime_contract(
    invariant_evaluation: LifecycleInvariantEvaluation,
) -> ProtectionRuntimeContract:
    policy_result = invariant_evaluation.policy_result
    decision = policy_result.decision

    if not invariant_evaluation.allowed:
        return ProtectionRuntimeContract(
            allowed=False,
            current_state=decision.current_state,
            next_state=None,
            required_action=ACTION_NONE,
            requires_authoritative_confirmation=False,
            requires_cleanup_confirmation=False,
            requires_trailing_confirmation=False,
            reason=policy_result.reason,
        )

    if decision.next_state == STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT:
        return ProtectionRuntimeContract(
            allowed=True,
            current_state=decision.current_state,
            next_state=decision.next_state,
            required_action=ACTION_ACCEPT_AUTHORITATIVE_EQUIVALENT,
            requires_authoritative_confirmation=True,
            requires_cleanup_confirmation=False,
            requires_trailing_confirmation=False,
            reason=decision.reason,
        )

    if decision.next_state == STATE_AUTHORITATIVE_REPLACEMENT_PENDING:
        return ProtectionRuntimeContract(
            allowed=True,
            current_state=decision.current_state,
            next_state=decision.next_state,
            required_action=ACTION_START_AUTHORITATIVE_REPLACEMENT,
            requires_authoritative_confirmation=True,
            requires_cleanup_confirmation=False,
            requires_trailing_confirmation=False,
            reason=decision.reason,
        )

    if decision.next_state == STATE_PROVISIONAL_CLEANUP_PENDING:
        action = ACTION_START_PROVISIONAL_CLEANUP

        if decision.current_state == STATE_STALE_PROVISIONAL_PRESENT:
            action = ACTION_RETRY_PROVISIONAL_CLEANUP

        return ProtectionRuntimeContract(
            allowed=True,
            current_state=decision.current_state,
            next_state=decision.next_state,
            required_action=action,
            requires_authoritative_confirmation=True,
            requires_cleanup_confirmation=True,
            requires_trailing_confirmation=False,
            reason=decision.reason,
        )

    if decision.next_state == STATE_AUTHORITATIVE_ACTIVE:
        return ProtectionRuntimeContract(
            allowed=True,
            current_state=decision.current_state,
            next_state=decision.next_state,
            required_action=ACTION_MARK_AUTHORITATIVE_ACTIVE,
            requires_authoritative_confirmation=True,
            requires_cleanup_confirmation=True,
            requires_trailing_confirmation=False,
            reason=decision.reason,
        )

    if decision.next_state == STATE_STALE_PROVISIONAL_PRESENT:
        return ProtectionRuntimeContract(
            allowed=True,
            current_state=decision.current_state,
            next_state=decision.next_state,
            required_action=ACTION_MARK_STALE_PROVISIONAL_PRESENT,
            requires_authoritative_confirmation=True,
            requires_cleanup_confirmation=True,
            requires_trailing_confirmation=False,
            reason=decision.reason,
        )

    if decision.next_state == STATE_TRAILING_READY:
        return ProtectionRuntimeContract(
            allowed=True,
            current_state=decision.current_state,
            next_state=decision.next_state,
            required_action=ACTION_ACTIVATE_TRAILING,
            requires_authoritative_confirmation=True,
            requires_cleanup_confirmation=False,
            requires_trailing_confirmation=True,
            reason=decision.reason,
        )

    return ProtectionRuntimeContract(
        allowed=False,
        current_state=decision.current_state,
        next_state=None,
        required_action=ACTION_NONE,
        requires_authoritative_confirmation=False,
        requires_cleanup_confirmation=False,
        requires_trailing_confirmation=False,
        reason=policy_result.reason,
    )
