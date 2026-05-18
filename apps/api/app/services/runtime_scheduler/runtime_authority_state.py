from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RuntimeAuthorityState(str, Enum):
    ACTIVE = "ACTIVE"
    INIT = "INIT"
    LOST_LOCK = "LOST_LOCK"
    LOCAL_IDENTITY_MISMATCH = "LOCAL_IDENTITY_MISMATCH"
    GENERATION_MISMATCH = "GENERATION_MISMATCH"
    STALE = "STALE"
    UNHEALTHY = "UNHEALTHY"
    INVALID = "INVALID"


@dataclass(frozen=True)
class RuntimeAuthorityStateProjection:
    state: RuntimeAuthorityState
    valid: bool
    reason: str | None
    operator_attention_required: bool


def project_runtime_authority_state(
    *,
    authority_valid: bool,
    authority_reason: str | None,
    advisory_session_reason: str | None,
) -> RuntimeAuthorityStateProjection:
    if authority_valid:
        return RuntimeAuthorityStateProjection(
            state=RuntimeAuthorityState.ACTIVE,
            valid=True,
            reason=None,
            operator_attention_required=False,
        )

    if authority_reason == "ownership_row_not_present":
        return RuntimeAuthorityStateProjection(
            state=RuntimeAuthorityState.INIT,
            valid=False,
            reason=authority_reason,
            operator_attention_required=False,
        )

    if authority_reason == "advisory_session_not_valid":
        state = RuntimeAuthorityState.LOST_LOCK if advisory_session_reason in {
            "advisory_session_connection_lost",
            "advisory_session_lock_lost",
            "advisory_session_release_failed",
        } else RuntimeAuthorityState.INIT

        return RuntimeAuthorityStateProjection(
            state=state,
            valid=False,
            reason=advisory_session_reason or authority_reason,
            operator_attention_required=state == RuntimeAuthorityState.LOST_LOCK,
        )

    if authority_reason == "local_identity_mismatch":
        return RuntimeAuthorityStateProjection(
            state=RuntimeAuthorityState.LOCAL_IDENTITY_MISMATCH,
            valid=False,
            reason=authority_reason,
            operator_attention_required=True,
        )

    if authority_reason == "runtime_generation_mismatch":
        return RuntimeAuthorityStateProjection(
            state=RuntimeAuthorityState.GENERATION_MISMATCH,
            valid=False,
            reason=authority_reason,
            operator_attention_required=True,
        )

    if authority_reason == "runtime_heartbeat_stale":
        return RuntimeAuthorityStateProjection(
            state=RuntimeAuthorityState.STALE,
            valid=False,
            reason=authority_reason,
            operator_attention_required=True,
        )

    if authority_reason == "runtime_health_invalid":
        return RuntimeAuthorityStateProjection(
            state=RuntimeAuthorityState.UNHEALTHY,
            valid=False,
            reason=authority_reason,
            operator_attention_required=True,
        )

    return RuntimeAuthorityStateProjection(
        state=RuntimeAuthorityState.INVALID,
        valid=False,
        reason=authority_reason or "runtime_authority_invalid",
        operator_attention_required=True,
    )
