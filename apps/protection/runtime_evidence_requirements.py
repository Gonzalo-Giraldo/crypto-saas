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
    ProtectionRuntimeContract,
)


EVIDENCE_AUTHORITATIVE_SL_ACTIVE = "AUTHORITATIVE_SL_ACTIVE"
EVIDENCE_AUTHORITATIVE_TP_ACTIVE = "AUTHORITATIVE_TP_ACTIVE"
EVIDENCE_PROVISIONAL_SL_ACTIVE = "PROVISIONAL_SL_ACTIVE"
EVIDENCE_PROVISIONAL_TP_ACTIVE = "PROVISIONAL_TP_ACTIVE"
EVIDENCE_ACTIVE_PROTECTION_VERIFIABLE = "ACTIVE_PROTECTION_VERIFIABLE"
EVIDENCE_RECONCILIATION_MATCHED = "RECONCILIATION_MATCHED"
EVIDENCE_SAFE_FOR_POSITION_UPDATE = "SAFE_FOR_POSITION_UPDATE"
EVIDENCE_CLEANUP_CONFIRMED = "CLEANUP_CONFIRMED"
EVIDENCE_STALE_PROVISIONAL_CONFIRMED = "STALE_PROVISIONAL_CONFIRMED"
EVIDENCE_BASELINE_STABLE = "BASELINE_STABLE"
EVIDENCE_TRAILING_NOT_ACTIVE = "TRAILING_NOT_ACTIVE"
EVIDENCE_TRAILING_CONFIRMED = "TRAILING_CONFIRMED"


@dataclass(frozen=True)
class RuntimeEvidenceRequirements:
    allowed: bool
    required_action: str
    required_evidence: tuple[str, ...]
    reason: str


def build_runtime_evidence_requirements(
    contract: ProtectionRuntimeContract,
) -> RuntimeEvidenceRequirements:
    if not contract.allowed:
        return RuntimeEvidenceRequirements(
            allowed=False,
            required_action=ACTION_NONE,
            required_evidence=tuple(),
            reason=contract.reason,
        )

    if contract.required_action == ACTION_ACCEPT_AUTHORITATIVE_EQUIVALENT:
        return RuntimeEvidenceRequirements(
            allowed=True,
            required_action=contract.required_action,
            required_evidence=(
                EVIDENCE_PROVISIONAL_SL_ACTIVE,
                EVIDENCE_PROVISIONAL_TP_ACTIVE,
                EVIDENCE_ACTIVE_PROTECTION_VERIFIABLE,
                EVIDENCE_RECONCILIATION_MATCHED,
                EVIDENCE_SAFE_FOR_POSITION_UPDATE,
            ),
            reason=contract.reason,
        )

    if contract.required_action == ACTION_START_AUTHORITATIVE_REPLACEMENT:
        return RuntimeEvidenceRequirements(
            allowed=True,
            required_action=contract.required_action,
            required_evidence=(
                EVIDENCE_PROVISIONAL_SL_ACTIVE,
                EVIDENCE_PROVISIONAL_TP_ACTIVE,
                EVIDENCE_ACTIVE_PROTECTION_VERIFIABLE,
                EVIDENCE_RECONCILIATION_MATCHED,
                EVIDENCE_SAFE_FOR_POSITION_UPDATE,
            ),
            reason=contract.reason,
        )

    if contract.required_action == ACTION_START_PROVISIONAL_CLEANUP:
        return RuntimeEvidenceRequirements(
            allowed=True,
            required_action=contract.required_action,
            required_evidence=(
                EVIDENCE_AUTHORITATIVE_SL_ACTIVE,
                EVIDENCE_AUTHORITATIVE_TP_ACTIVE,
                EVIDENCE_ACTIVE_PROTECTION_VERIFIABLE,
            ),
            reason=contract.reason,
        )

    if contract.required_action == ACTION_MARK_AUTHORITATIVE_ACTIVE:
        return RuntimeEvidenceRequirements(
            allowed=True,
            required_action=contract.required_action,
            required_evidence=(
                EVIDENCE_AUTHORITATIVE_SL_ACTIVE,
                EVIDENCE_AUTHORITATIVE_TP_ACTIVE,
                EVIDENCE_ACTIVE_PROTECTION_VERIFIABLE,
                EVIDENCE_CLEANUP_CONFIRMED,
            ),
            reason=contract.reason,
        )

    if contract.required_action == ACTION_MARK_STALE_PROVISIONAL_PRESENT:
        return RuntimeEvidenceRequirements(
            allowed=True,
            required_action=contract.required_action,
            required_evidence=(
                EVIDENCE_AUTHORITATIVE_SL_ACTIVE,
                EVIDENCE_AUTHORITATIVE_TP_ACTIVE,
                EVIDENCE_ACTIVE_PROTECTION_VERIFIABLE,
                EVIDENCE_STALE_PROVISIONAL_CONFIRMED,
            ),
            reason=contract.reason,
        )

    if contract.required_action == ACTION_RETRY_PROVISIONAL_CLEANUP:
        return RuntimeEvidenceRequirements(
            allowed=True,
            required_action=contract.required_action,
            required_evidence=(
                EVIDENCE_AUTHORITATIVE_SL_ACTIVE,
                EVIDENCE_AUTHORITATIVE_TP_ACTIVE,
                EVIDENCE_ACTIVE_PROTECTION_VERIFIABLE,
                EVIDENCE_STALE_PROVISIONAL_CONFIRMED,
            ),
            reason=contract.reason,
        )

    if contract.required_action == ACTION_ACTIVATE_TRAILING:
        return RuntimeEvidenceRequirements(
            allowed=True,
            required_action=contract.required_action,
            required_evidence=(
                EVIDENCE_AUTHORITATIVE_SL_ACTIVE,
                EVIDENCE_AUTHORITATIVE_TP_ACTIVE,
                EVIDENCE_ACTIVE_PROTECTION_VERIFIABLE,
                EVIDENCE_BASELINE_STABLE,
                EVIDENCE_TRAILING_NOT_ACTIVE,
                EVIDENCE_TRAILING_CONFIRMED,
            ),
            reason=contract.reason,
        )

    return RuntimeEvidenceRequirements(
        allowed=False,
        required_action=ACTION_NONE,
        required_evidence=tuple(),
        reason=contract.reason,
    )
