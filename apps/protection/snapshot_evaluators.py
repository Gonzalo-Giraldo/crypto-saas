from apps.protection.cleanup_evaluator import can_start_cleanup
from apps.protection.cleanup_result_evaluator import evaluate_cleanup_result
from apps.protection.equivalent_evaluator import (
    can_accept_authoritative_equivalent,
)
from apps.protection.evidence_snapshot import ProtectionEvidenceSnapshot
from apps.protection.protection_decision import ProtectionDecision
from apps.protection.replacement_evaluator import (
    can_start_authoritative_replacement,
)
from apps.protection.retry_cleanup_evaluator import can_retry_cleanup
from apps.protection.trailing_evaluator import can_activate_trailing


def evaluate_equivalent_from_snapshot(
    snapshot: ProtectionEvidenceSnapshot,
) -> ProtectionDecision:
    return can_accept_authoritative_equivalent(
        current_state=snapshot.current_state,
        reconciliation_status=snapshot.reconciliation_status,
        safe_for_position_update=snapshot.safe_for_position_update,
        correction_required=snapshot.correction_required,
        provisional_sl_active=snapshot.provisional_sl_active,
        provisional_tp_active=snapshot.provisional_tp_active,
        active_protection_verifiable=snapshot.active_protection_verifiable,
        replacement_not_started=snapshot.replacement_not_started,
    )


def evaluate_replacement_from_snapshot(
    snapshot: ProtectionEvidenceSnapshot,
) -> ProtectionDecision:
    return can_start_authoritative_replacement(
        current_state=snapshot.current_state,
        reconciliation_status=snapshot.reconciliation_status,
        safe_for_position_update=snapshot.safe_for_position_update,
        correction_required=snapshot.correction_required,
        provisional_sl_active=snapshot.provisional_sl_active,
        provisional_tp_active=snapshot.provisional_tp_active,
        active_protection_verifiable=snapshot.active_protection_verifiable,
        replacement_not_started=snapshot.replacement_not_started,
    )


def evaluate_cleanup_start_from_snapshot(
    snapshot: ProtectionEvidenceSnapshot,
) -> ProtectionDecision:
    return can_start_cleanup(
        current_state=snapshot.current_state,
        authoritative_sl_active=snapshot.authoritative_sl_active,
        authoritative_tp_active=snapshot.authoritative_tp_active,
        active_protection_verifiable=snapshot.active_protection_verifiable,
    )


def evaluate_cleanup_result_from_snapshot(
    snapshot: ProtectionEvidenceSnapshot,
) -> ProtectionDecision:
    return evaluate_cleanup_result(
        current_state=snapshot.current_state,
        cleanup_successful=snapshot.cleanup_successful,
        stale_provisional_present=snapshot.stale_provisional_present,
        authoritative_sl_active=snapshot.authoritative_sl_active,
        authoritative_tp_active=snapshot.authoritative_tp_active,
        active_protection_verifiable=snapshot.active_protection_verifiable,
    )


def evaluate_cleanup_retry_from_snapshot(
    snapshot: ProtectionEvidenceSnapshot,
) -> ProtectionDecision:
    return can_retry_cleanup(
        current_state=snapshot.current_state,
        authoritative_sl_active=snapshot.authoritative_sl_active,
        authoritative_tp_active=snapshot.authoritative_tp_active,
        active_protection_verifiable=snapshot.active_protection_verifiable,
        stale_provisional_present=snapshot.stale_provisional_present,
        cleanup_retry_allowed=snapshot.cleanup_retry_allowed,
    )


def evaluate_trailing_from_snapshot(
    snapshot: ProtectionEvidenceSnapshot,
) -> ProtectionDecision:
    return can_activate_trailing(
        current_state=snapshot.current_state,
        baseline_stable=snapshot.baseline_stable,
        active_protection_verifiable=snapshot.active_protection_verifiable,
        authoritative_sl_active=snapshot.authoritative_sl_active,
        authoritative_tp_active=snapshot.authoritative_tp_active,
        trailing_not_active=snapshot.trailing_not_active,
    )
