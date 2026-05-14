from apps.worker.app.engine.binance_protection_reconciliation import (
    reconcile_exit_protection_state,
)


def test_reconcile_protected_when_sl_and_tp_active():
    result = reconcile_exit_protection_state(
        sl_classification="ACTIVE_EVIDENCE_PRESENT",
        tp_classification="ACTIVE_EVIDENCE_PRESENT",
        sl_fetch_status="OK",
        tp_fetch_status="OK",
    )
    assert result["protection_state"] == "PROTECTED"
    assert result["protection_active_verifiable"] is True
    assert result["protection_unknown"] is False


def test_reconcile_partially_protected_when_only_one_active():
    result = reconcile_exit_protection_state(
        sl_classification="ACTIVE_EVIDENCE_PRESENT",
        tp_classification="INACTIVE_PROTECTION",
        sl_fetch_status="OK",
        tp_fetch_status="OK",
    )
    assert result["protection_state"] == "PARTIALLY_PROTECTED"
    assert result["protection_active_verifiable"] is False


def test_reconcile_triggered_when_any_leg_triggered():
    result = reconcile_exit_protection_state(
        sl_classification="TRIGGERED_OR_FILLED",
        tp_classification="ACTIVE_EVIDENCE_PRESENT",
        sl_fetch_status="OK",
        tp_fetch_status="OK",
    )
    assert result["protection_state"] == "TRIGGERED"
    assert result["protection_triggered"] is True


def test_reconcile_expired_when_both_inactive():
    result = reconcile_exit_protection_state(
        sl_classification="INACTIVE_PROTECTION",
        tp_classification="INACTIVE_PROTECTION",
        sl_fetch_status="OK",
        tp_fetch_status="OK",
    )
    assert result["protection_state"] == "EXPIRED"


def test_reconcile_unknown_on_fetch_timeout():
    result = reconcile_exit_protection_state(
        sl_classification="ACTIVE_EVIDENCE_PRESENT",
        tp_classification="ACTIVE_EVIDENCE_PRESENT",
        sl_fetch_status="OK",
        tp_fetch_status="TIMEOUT",
    )
    assert result["protection_state"] == "PROTECTION_UNKNOWN"
    assert result["protection_unknown"] is True


def test_reconcile_unknown_on_unknown_classification():
    result = reconcile_exit_protection_state(
        sl_classification="UNKNOWN",
        tp_classification="ACTIVE_EVIDENCE_PRESENT",
        sl_fetch_status="OK",
        tp_fetch_status="OK",
    )
    assert result["protection_state"] == "PROTECTION_UNKNOWN"


def test_reconcile_unprotected_when_no_active_and_no_terminal():
    result = reconcile_exit_protection_state(
        sl_classification="INACTIVE_PROTECTION",
        tp_classification="UNKNOWN_EMPTY_ALLOWED",
        sl_fetch_status="OK",
        tp_fetch_status="OK",
    )
    assert result["protection_state"] == "UNPROTECTED"
