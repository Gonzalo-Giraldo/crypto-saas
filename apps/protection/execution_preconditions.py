from dataclasses import dataclass

from apps.protection.runtime_contract import (
    ACTION_ACCEPT_AUTHORITATIVE_EQUIVALENT,
    ACTION_ACTIVATE_TRAILING,
    ACTION_MARK_AUTHORITATIVE_ACTIVE,
    ACTION_MARK_STALE_PROVISIONAL_PRESENT,
    ACTION_NONE,
    ACTION_RETRY_PROVISIONAL_CLEANUP,
    ACTION_START_AUTHORITATIVE_REPLACEMENT,
    ACTION_START_PROVISIONAL_CLEANUP,
)
from apps.protection.runtime_evidence_requirements import (
    EVIDENCE_ACTIVE_PROTECTION_VERIFIABLE,
    EVIDENCE_AUTHORITATIVE_SL_ACTIVE,
    EVIDENCE_AUTHORITATIVE_TP_ACTIVE,
    EVIDENCE_BASELINE_STABLE,
    EVIDENCE_CLEANUP_CONFIRMED,
    EVIDENCE_PROVISIONAL_SL_ACTIVE,
    EVIDENCE_PROVISIONAL_TP_ACTIVE,
    EVIDENCE_RECONCILIATION_MATCHED,
    EVIDENCE_SAFE_FOR_POSITION_UPDATE,
    EVIDENCE_STALE_PROVISIONAL_CONFIRMED,
    EVIDENCE_TRAILING_CONFIRMED,
    EVIDENCE_TRAILING_NOT_ACTIVE,
    RuntimeEvidenceRequirements,
)


PRECONDITION_NO_EXECUTION_FOR_DENIED_CONTRACT = (
    "NO_EXECUTION_FOR_DENIED_CONTRACT"
)
PRECONDITION_ACTIVE_PROTECTION_VERIFIED = (
    "ACTIVE_PROTECTION_VERIFIED"
)
PRECONDITION_RECONCILIATION_MATCHED = (
    "RECONCILIATION_MATCHED"
)
PRECONDITION_SAFE_FOR_POSITION_UPDATE = (
    "SAFE_FOR_POSITION_UPDATE"
)
PRECONDITION_PROVISIONAL_PROTECTION_PRESENT = (
    "PROVISIONAL_PROTECTION_PRESENT"
)
PRECONDITION_AUTHORITATIVE_PROTECTION_PRESENT = (
    "AUTHORITATIVE_PROTECTION_PRESENT"
)
PRECONDITION_CLEANUP_CONFIRMED = (
    "CLEANUP_CONFIRMED"
)
PRECONDITION_STALE_PROVISIONAL_CONFIRMED = (
    "STALE_PROVISIONAL_CONFIRMED"
)
PRECONDITION_BASELINE_STABLE = (
    "BASELINE_STABLE"
)
PRECONDITION_TRAILING_READY_TO_ACTIVATE = (
    "TRAILING_READY_TO_ACTIVATE"
)
PRECONDITION_TRAILING_CONFIRMED = (
    "TRAILING_CONFIRMED"
)


@dataclass(frozen=True)
class ExecutionPreconditions:
    allowed: bool
    required_action: str
    required_preconditions: tuple[str, ...]
    reason: str


def build_execution_preconditions(
    requirements: RuntimeEvidenceRequirements,
) -> ExecutionPreconditions:
    if not requirements.allowed:
        return ExecutionPreconditions(
            allowed=False,
            required_action=ACTION_NONE,
            required_preconditions=(
                PRECONDITION_NO_EXECUTION_FOR_DENIED_CONTRACT,
            ),
            reason=requirements.reason,
        )

    evidence = set(requirements.required_evidence)

    preconditions: list[str] = []

    if EVIDENCE_ACTIVE_PROTECTION_VERIFIABLE in evidence:
        preconditions.append(PRECONDITION_ACTIVE_PROTECTION_VERIFIED)

    if EVIDENCE_RECONCILIATION_MATCHED in evidence:
        preconditions.append(PRECONDITION_RECONCILIATION_MATCHED)

    if EVIDENCE_SAFE_FOR_POSITION_UPDATE in evidence:
        preconditions.append(PRECONDITION_SAFE_FOR_POSITION_UPDATE)

    if (
        EVIDENCE_PROVISIONAL_SL_ACTIVE in evidence
        and EVIDENCE_PROVISIONAL_TP_ACTIVE in evidence
    ):
        preconditions.append(PRECONDITION_PROVISIONAL_PROTECTION_PRESENT)

    if (
        EVIDENCE_AUTHORITATIVE_SL_ACTIVE in evidence
        and EVIDENCE_AUTHORITATIVE_TP_ACTIVE in evidence
    ):
        preconditions.append(PRECONDITION_AUTHORITATIVE_PROTECTION_PRESENT)

    if EVIDENCE_CLEANUP_CONFIRMED in evidence:
        preconditions.append(PRECONDITION_CLEANUP_CONFIRMED)

    if EVIDENCE_STALE_PROVISIONAL_CONFIRMED in evidence:
        preconditions.append(PRECONDITION_STALE_PROVISIONAL_CONFIRMED)

    if EVIDENCE_BASELINE_STABLE in evidence:
        preconditions.append(PRECONDITION_BASELINE_STABLE)

    if EVIDENCE_TRAILING_NOT_ACTIVE in evidence:
        preconditions.append(PRECONDITION_TRAILING_READY_TO_ACTIVATE)

    if EVIDENCE_TRAILING_CONFIRMED in evidence:
        preconditions.append(PRECONDITION_TRAILING_CONFIRMED)

    return ExecutionPreconditions(
        allowed=True,
        required_action=requirements.required_action,
        required_preconditions=tuple(preconditions),
        reason=requirements.reason,
    )
