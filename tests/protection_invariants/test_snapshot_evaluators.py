from apps.protection.constants import (
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_ACTIVE,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_STALE_PROVISIONAL_PRESENT,
    STATE_TRAILING_READY,
)

from apps.protection.evidence_snapshot import ProtectionEvidenceSnapshot
from apps.protection.snapshot_evaluators import (
    evaluate_cleanup_result_from_snapshot,
    evaluate_cleanup_retry_from_snapshot,
    evaluate_cleanup_start_from_snapshot,
    evaluate_equivalent_from_snapshot,
    evaluate_replacement_from_snapshot,
    evaluate_trailing_from_snapshot,
)


def snapshot_for_state(current_state: str) -> ProtectionEvidenceSnapshot:
    return ProtectionEvidenceSnapshot(
        current_state=current_state,
        reconciliation_status="matched",
        safe_for_position_update=True,
        correction_required=False,
        provisional_sl_active=True,
        provisional_tp_active=True,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        active_protection_verifiable=True,
        replacement_not_started=True,
        cleanup_successful=True,
        stale_provisional_present=False,
        cleanup_retry_allowed=True,
        baseline_stable=True,
        trailing_not_active=True,
    )


def test_equivalent_evaluator_uses_snapshot_evidence():
    decision = evaluate_equivalent_from_snapshot(
        snapshot_for_state(STATE_PROVISIONAL_ACTIVE)
    )

    assert decision.allowed is True
    assert decision.next_state == STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT


def test_replacement_evaluator_uses_snapshot_evidence():
    snapshot = ProtectionEvidenceSnapshot(
        current_state=STATE_PROVISIONAL_ACTIVE,
        reconciliation_status="matched",
        safe_for_position_update=True,
        correction_required=True,
        provisional_sl_active=True,
        provisional_tp_active=True,
        authoritative_sl_active=False,
        authoritative_tp_active=False,
        active_protection_verifiable=True,
        replacement_not_started=True,
        cleanup_successful=False,
        stale_provisional_present=False,
        cleanup_retry_allowed=False,
        baseline_stable=False,
        trailing_not_active=True,
    )

    decision = evaluate_replacement_from_snapshot(snapshot)

    assert decision.allowed is True
    assert decision.next_state == STATE_AUTHORITATIVE_REPLACEMENT_PENDING


def test_cleanup_start_evaluator_uses_snapshot_evidence():
    decision = evaluate_cleanup_start_from_snapshot(
        snapshot_for_state(STATE_AUTHORITATIVE_REPLACEMENT_PENDING)
    )

    assert decision.allowed is True
    assert decision.next_state == STATE_PROVISIONAL_CLEANUP_PENDING


def test_cleanup_result_evaluator_uses_snapshot_evidence_success():
    decision = evaluate_cleanup_result_from_snapshot(
        snapshot_for_state(STATE_PROVISIONAL_CLEANUP_PENDING)
    )

    assert decision.allowed is True
    assert decision.next_state == STATE_AUTHORITATIVE_ACTIVE


def test_cleanup_result_evaluator_uses_snapshot_evidence_stale():
    snapshot = ProtectionEvidenceSnapshot(
        current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
        reconciliation_status="matched",
        safe_for_position_update=True,
        correction_required=False,
        provisional_sl_active=True,
        provisional_tp_active=True,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        active_protection_verifiable=True,
        replacement_not_started=True,
        cleanup_successful=False,
        stale_provisional_present=True,
        cleanup_retry_allowed=True,
        baseline_stable=True,
        trailing_not_active=True,
    )

    decision = evaluate_cleanup_result_from_snapshot(snapshot)

    assert decision.allowed is True
    assert decision.next_state == STATE_STALE_PROVISIONAL_PRESENT


def test_cleanup_retry_evaluator_uses_snapshot_evidence():
    snapshot = ProtectionEvidenceSnapshot(
        current_state=STATE_STALE_PROVISIONAL_PRESENT,
        reconciliation_status="matched",
        safe_for_position_update=True,
        correction_required=False,
        provisional_sl_active=True,
        provisional_tp_active=True,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        active_protection_verifiable=True,
        replacement_not_started=True,
        cleanup_successful=False,
        stale_provisional_present=True,
        cleanup_retry_allowed=True,
        baseline_stable=True,
        trailing_not_active=True,
    )

    decision = evaluate_cleanup_retry_from_snapshot(snapshot)

    assert decision.allowed is True
    assert decision.next_state == STATE_PROVISIONAL_CLEANUP_PENDING


def test_trailing_evaluator_uses_snapshot_evidence():
    decision = evaluate_trailing_from_snapshot(
        snapshot_for_state(STATE_AUTHORITATIVE_ACTIVE)
    )

    assert decision.allowed is True
    assert decision.next_state == STATE_TRAILING_READY


def test_snapshot_equivalent_rejects_unmatched_reconciliation():
    snapshot = ProtectionEvidenceSnapshot(
        current_state=STATE_PROVISIONAL_ACTIVE,
        reconciliation_status="unmatched",
        safe_for_position_update=True,
        correction_required=False,
        provisional_sl_active=True,
        provisional_tp_active=True,
        authoritative_sl_active=False,
        authoritative_tp_active=False,
        active_protection_verifiable=True,
        replacement_not_started=True,
        cleanup_successful=False,
        stale_provisional_present=False,
        cleanup_retry_allowed=False,
        baseline_stable=False,
        trailing_not_active=True,
    )

    decision = evaluate_equivalent_from_snapshot(snapshot)

    assert decision.allowed is False
    assert decision.next_state is None


def test_snapshot_replacement_rejects_unverifiable_protection():
    snapshot = ProtectionEvidenceSnapshot(
        current_state=STATE_PROVISIONAL_ACTIVE,
        reconciliation_status="matched",
        safe_for_position_update=True,
        correction_required=True,
        provisional_sl_active=True,
        provisional_tp_active=True,
        authoritative_sl_active=False,
        authoritative_tp_active=False,
        active_protection_verifiable=False,
        replacement_not_started=True,
        cleanup_successful=False,
        stale_provisional_present=False,
        cleanup_retry_allowed=False,
        baseline_stable=False,
        trailing_not_active=True,
    )

    decision = evaluate_replacement_from_snapshot(snapshot)

    assert decision.allowed is False
    assert decision.next_state is None


def test_snapshot_cleanup_start_rejects_missing_authoritative_leg():
    snapshot = ProtectionEvidenceSnapshot(
        current_state=STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
        reconciliation_status="matched",
        safe_for_position_update=True,
        correction_required=True,
        provisional_sl_active=True,
        provisional_tp_active=True,
        authoritative_sl_active=True,
        authoritative_tp_active=False,
        active_protection_verifiable=True,
        replacement_not_started=False,
        cleanup_successful=False,
        stale_provisional_present=False,
        cleanup_retry_allowed=False,
        baseline_stable=False,
        trailing_not_active=True,
    )

    decision = evaluate_cleanup_start_from_snapshot(snapshot)

    assert decision.allowed is False
    assert decision.next_state is None


def test_snapshot_trailing_rejects_unstable_baseline():
    snapshot = ProtectionEvidenceSnapshot(
        current_state=STATE_AUTHORITATIVE_ACTIVE,
        reconciliation_status="matched",
        safe_for_position_update=True,
        correction_required=False,
        provisional_sl_active=True,
        provisional_tp_active=True,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        active_protection_verifiable=True,
        replacement_not_started=False,
        cleanup_successful=True,
        stale_provisional_present=False,
        cleanup_retry_allowed=False,
        baseline_stable=False,
        trailing_not_active=True,
    )

    decision = evaluate_trailing_from_snapshot(snapshot)

    assert decision.allowed is False
    assert decision.next_state is None
