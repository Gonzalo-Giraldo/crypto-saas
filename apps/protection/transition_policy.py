from dataclasses import dataclass

from apps.protection.constants import (
    REASON_INVALID_CURRENT_STATE,
    REASON_PROTECTION_NOT_VERIFIABLE,
)
from apps.protection.decision_trace import LifecycleDecisionTrace
from apps.protection.protection_decision import ProtectionDecision
from apps.protection.transition_assertions import assert_allowed_transition


@dataclass(frozen=True)
class TransitionPolicyResult:
    allowed: bool
    reason: str
    decision: ProtectionDecision


def authorize_traced_transition(
    trace: LifecycleDecisionTrace,
) -> TransitionPolicyResult:
    decision = trace.final_decision

    if not decision.allowed:
        return TransitionPolicyResult(
            allowed=False,
            reason=decision.reason,
            decision=decision,
        )

    if decision.next_state is None:
        return TransitionPolicyResult(
            allowed=False,
            reason=REASON_INVALID_CURRENT_STATE,
            decision=ProtectionDecision(
                allowed=False,
                reason=REASON_INVALID_CURRENT_STATE,
                current_state=decision.current_state,
                next_state=None,
            ),
        )

    registry_decision = assert_allowed_transition(
        current_state=decision.current_state,
        next_state=decision.next_state,
    )

    if not registry_decision.allowed:
        return TransitionPolicyResult(
            allowed=False,
            reason=registry_decision.reason,
            decision=registry_decision,
        )

    if not trace.accepted_steps:
        return TransitionPolicyResult(
            allowed=False,
            reason=REASON_INVALID_CURRENT_STATE,
            decision=ProtectionDecision(
                allowed=False,
                reason=REASON_INVALID_CURRENT_STATE,
                current_state=decision.current_state,
                next_state=None,
            ),
        )

    accepted_step = trace.accepted_steps[-1].decision

    if accepted_step.current_state != decision.current_state:
        return TransitionPolicyResult(
            allowed=False,
            reason=REASON_PROTECTION_NOT_VERIFIABLE,
            decision=ProtectionDecision(
                allowed=False,
                reason=REASON_PROTECTION_NOT_VERIFIABLE,
                current_state=decision.current_state,
                next_state=None,
            ),
        )

    if accepted_step.next_state != decision.next_state:
        return TransitionPolicyResult(
            allowed=False,
            reason=REASON_PROTECTION_NOT_VERIFIABLE,
            decision=ProtectionDecision(
                allowed=False,
                reason=REASON_PROTECTION_NOT_VERIFIABLE,
                current_state=decision.current_state,
                next_state=None,
            ),
        )

    return TransitionPolicyResult(
        allowed=True,
        reason=decision.reason,
        decision=decision,
    )
