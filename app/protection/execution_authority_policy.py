from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Tuple


class ExecutionAuthorityClass(str, Enum):
    PROVISIONAL_PROTECTION_AUTHORITY = "PROVISIONAL_PROTECTION_AUTHORITY"
    AUTHORITATIVE_PROTECTION_AUTHORITY = "AUTHORITATIVE_PROTECTION_AUTHORITY"
    REPLACEMENT_AUTHORITY = "REPLACEMENT_AUTHORITY"
    CLEANUP_AUTHORITY = "CLEANUP_AUTHORITY"
    TRAILING_AUTHORITY = "TRAILING_AUTHORITY"


class ExecutionIntent(str, Enum):
    CREATE_AUTHORITATIVE_EXIT = "CREATE_AUTHORITATIVE_EXIT"
    REPLACE_AUTHORITATIVE_EXIT = "REPLACE_AUTHORITATIVE_EXIT"
    CANCEL_PROVISIONAL_EXIT = "CANCEL_PROVISIONAL_EXIT"
    CLEANUP_STALE_PROVISIONAL = "CLEANUP_STALE_PROVISIONAL"
    ARM_TRAILING = "ARM_TRAILING"
    NOOP = "NOOP"


class ExecutionAuthorityPolicyReason(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    EXECUTION_NOT_AUTHORIZED = "EXECUTION_NOT_AUTHORIZED"
    MISSING_REQUIRED_AUTHORITY = "MISSING_REQUIRED_AUTHORITY"
    FORBIDDEN_INTENT = "FORBIDDEN_INTENT"
    AUTHORITY_INTENT_MISMATCH = "AUTHORITY_INTENT_MISMATCH"
    STABLE_BASELINE_REQUIRED = "STABLE_BASELINE_REQUIRED"
    AUTHORITATIVE_OWNERSHIP_REQUIRED = "AUTHORITATIVE_OWNERSHIP_REQUIRED"
    PROTECTION_CONTINUITY_REQUIRED = "PROTECTION_CONTINUITY_REQUIRED"


@dataclass(frozen=True)
class ExecutionAuthorityPolicy:
    required_authorities: FrozenSet[ExecutionAuthorityClass]
    allowed_intents: FrozenSet[ExecutionIntent]
    forbidden_intents: FrozenSet[ExecutionIntent]
    requires_authoritative_ownership: bool = True
    requires_stable_baseline: bool = True
    requires_protection_continuity: bool = True


@dataclass(frozen=True)
class ExecutionAuthorityEvidence:
    granted_authorities: FrozenSet[ExecutionAuthorityClass]
    requested_intents: FrozenSet[ExecutionIntent]
    authoritative_ownership_proven: bool
    stable_baseline_proven: bool
    protection_continuity_proven: bool


@dataclass(frozen=True)
class ExecutionAuthorityPolicyDecision:
    allowed: bool
    reason: ExecutionAuthorityPolicyReason
    missing_authorities: Tuple[ExecutionAuthorityClass, ...]
    rejected_intents: Tuple[ExecutionIntent, ...]
    forbidden_intents: Tuple[ExecutionIntent, ...]


def evaluate_execution_authority_policy(
    *,
    execution_authorization_allowed: bool,
    policy: ExecutionAuthorityPolicy,
    evidence: ExecutionAuthorityEvidence,
) -> ExecutionAuthorityPolicyDecision:
    """
    Pure deterministic execution authority policy evaluator.

    This function does not authenticate users.
    It does not inspect sessions, tokens, DB records, runtime ownership, broker state,
    Binance state, websocket state, time, IO, or async orchestration.

    It only evaluates semantic authority requirements for a future execution layer.
    """

    if not execution_authorization_allowed:
        return ExecutionAuthorityPolicyDecision(
            allowed=False,
            reason=ExecutionAuthorityPolicyReason.EXECUTION_NOT_AUTHORIZED,
            missing_authorities=(),
            rejected_intents=(),
            forbidden_intents=(),
        )

    missing_authorities = tuple(
        sorted(
            policy.required_authorities - evidence.granted_authorities,
            key=lambda item: item.value,
        )
    )
    if missing_authorities:
        return ExecutionAuthorityPolicyDecision(
            allowed=False,
            reason=ExecutionAuthorityPolicyReason.MISSING_REQUIRED_AUTHORITY,
            missing_authorities=missing_authorities,
            rejected_intents=(),
            forbidden_intents=(),
        )

    forbidden_intents = tuple(
        sorted(
            evidence.requested_intents & policy.forbidden_intents,
            key=lambda item: item.value,
        )
    )
    if forbidden_intents:
        return ExecutionAuthorityPolicyDecision(
            allowed=False,
            reason=ExecutionAuthorityPolicyReason.FORBIDDEN_INTENT,
            missing_authorities=(),
            rejected_intents=(),
            forbidden_intents=forbidden_intents,
        )

    rejected_intents = tuple(
        sorted(
            evidence.requested_intents - policy.allowed_intents,
            key=lambda item: item.value,
        )
    )
    if rejected_intents:
        return ExecutionAuthorityPolicyDecision(
            allowed=False,
            reason=ExecutionAuthorityPolicyReason.AUTHORITY_INTENT_MISMATCH,
            missing_authorities=(),
            rejected_intents=rejected_intents,
            forbidden_intents=(),
        )

    if (
        policy.requires_authoritative_ownership
        and not evidence.authoritative_ownership_proven
    ):
        return ExecutionAuthorityPolicyDecision(
            allowed=False,
            reason=ExecutionAuthorityPolicyReason.AUTHORITATIVE_OWNERSHIP_REQUIRED,
            missing_authorities=(),
            rejected_intents=(),
            forbidden_intents=(),
        )

    if policy.requires_stable_baseline and not evidence.stable_baseline_proven:
        return ExecutionAuthorityPolicyDecision(
            allowed=False,
            reason=ExecutionAuthorityPolicyReason.STABLE_BASELINE_REQUIRED,
            missing_authorities=(),
            rejected_intents=(),
            forbidden_intents=(),
        )

    if (
        policy.requires_protection_continuity
        and not evidence.protection_continuity_proven
    ):
        return ExecutionAuthorityPolicyDecision(
            allowed=False,
            reason=ExecutionAuthorityPolicyReason.PROTECTION_CONTINUITY_REQUIRED,
            missing_authorities=(),
            rejected_intents=(),
            forbidden_intents=(),
        )

    return ExecutionAuthorityPolicyDecision(
        allowed=True,
        reason=ExecutionAuthorityPolicyReason.AUTHORIZED,
        missing_authorities=(),
        rejected_intents=(),
        forbidden_intents=(),
    )
