from apps.protection.constants import (
    REASON_INVALID_CURRENT_STATE,
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_ACTIVE,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_STALE_PROVISIONAL_PRESENT,
    STATE_TRAILING_READY,
)

from apps.protection.evidence_snapshot import ProtectionEvidenceSnapshot
from apps.protection.lifecycle_engine import evaluate_lifecycle_from_snapshot


def snapshot(
    *,
    current_state: str,
    correction_required: bool = False,
    cleanup_successful: bool = True,
    stale_provisional_present: bool = False,
    baseline_stable: bool = True,
    active_protection_verifiable: bool = True,
    authoritative_sl_active: bool = True,
    authoritative_tp_active: bool = True,
    provisional_sl_active: bool = True,
    provisional_tp_active: bool = True,
    reconciliation_status: str = "matched",
    safe_for_position_update: bool = True,
    replacement_not_started: bool = True,
    cleanup_retry_allowed: bool = True,
    trailing_not_active: bool = True,
) -> ProtectionEvidenceSnapshot:
    return ProtectionEvidenceSnapshot(
        current_state=current_state,
        reconciliation_status=reconciliation_status,
        safe_for_position_update=safe_for_position_update,
        correction_required=correction_required,
        provisional_sl_active=provisional_sl_active,
        provisional_tp_active=provisional_tp_active,
        authoritative_sl_active=authoritative_sl_active,
        authoritative_tp_active=authoritative_tp_active,
        active_protection_verifiable=active_protection_verifiable,
        replacement_not_started=replacement_not_started,
        cleanup_successful=cleanup_successful,
        stale_provisional_present=stale_provisional_present,
        cleanup_retry_allowed=cleanup_retry_allowed,
        baseline_stable=baseline_stable,
        trailing_not_active=trailing_not_active,
    )


def test_engine_selects_equivalent_path_when_no_correction_required():
    decision = evaluate_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=False,
        )
    )

    assert decision.allowed is True
    assert decision.next_state == STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT


def test_engine_selects_replacement_path_when_correction_required():
    decision = evaluate_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            correction_required=True,
        )
    )

    assert decision.allowed is True
    assert decision.next_state == STATE_AUTHORITATIVE_REPLACEMENT_PENDING


def test_engine_starts_cleanup_only_after_authoritative_replacement_pending():
    decision = evaluate_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
        )
    )

    assert decision.allowed is True
    assert decision.next_state == STATE_PROVISIONAL_CLEANUP_PENDING


def test_engine_accepts_cleanup_success_as_authoritative_active():
    decision = evaluate_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
            cleanup_successful=True,
            stale_provisional_present=False,
        )
    )

    assert decision.allowed is True
    assert decision.next_state == STATE_AUTHORITATIVE_ACTIVE


def test_engine_preserves_protection_on_cleanup_failure_with_stale_present():
    decision = evaluate_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
            cleanup_successful=False,
            stale_provisional_present=True,
        )
    )

    assert decision.allowed is True
    assert decision.next_state == STATE_STALE_PROVISIONAL_PRESENT


def test_engine_retries_cleanup_from_stale_provisional_only():
    decision = evaluate_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_STALE_PROVISIONAL_PRESENT,
            stale_provisional_present=True,
            cleanup_retry_allowed=True,
        )
    )

    assert decision.allowed is True
    assert decision.next_state == STATE_PROVISIONAL_CLEANUP_PENDING


def test_engine_activates_trailing_from_authoritative_active():
    decision = evaluate_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_AUTHORITATIVE_ACTIVE,
            baseline_stable=True,
        )
    )

    assert decision.allowed is True
    assert decision.next_state == STATE_TRAILING_READY


def test_engine_activates_trailing_from_equivalent_authoritative_active():
    decision = evaluate_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
            baseline_stable=True,
        )
    )

    assert decision.allowed is True
    assert decision.next_state == STATE_TRAILING_READY


def test_engine_rejects_unknown_state():
    decision = evaluate_lifecycle_from_snapshot(
        snapshot(
            current_state="UNKNOWN_STATE",
        )
    )

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.next_state is None


def test_engine_rejects_unmatched_reconciliation_from_provisional():
    decision = evaluate_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_PROVISIONAL_ACTIVE,
            reconciliation_status="unmatched",
        )
    )

    assert decision.allowed is False
    assert decision.next_state is None


def test_engine_rejects_unverifiable_cleanup_start():
    decision = evaluate_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
            active_protection_verifiable=False,
        )
    )

    assert decision.allowed is False
    assert decision.next_state is None


def test_engine_rejects_unstable_trailing_baseline():
    decision = evaluate_lifecycle_from_snapshot(
        snapshot(
            current_state=STATE_AUTHORITATIVE_ACTIVE,
            baseline_stable=False,
        )
    )

    assert decision.allowed is False
    assert decision.next_state is None
