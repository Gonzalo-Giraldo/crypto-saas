from apps.protection.constants import (
    STATE_PROVISIONAL_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    REASON_OK,
    REASON_INVALID_CURRENT_STATE,
    REASON_RECONCILIATION_NOT_MATCHED,
    REASON_CORRECTION_NOT_REQUIRED,
    REASON_PROTECTION_NOT_VERIFIABLE,
)

from apps.protection.replacement_evaluator import can_start_authoritative_replacement


def valid_kwargs():
    return dict(
        current_state=STATE_PROVISIONAL_ACTIVE,
        reconciliation_status="matched",
        safe_for_position_update=True,
        correction_required=True,
        provisional_sl_active=True,
        provisional_tp_active=True,
        active_protection_verifiable=True,
        replacement_not_started=True,
    )


def test_starts_authoritative_replacement_when_all_evidence_is_valid():
    decision = can_start_authoritative_replacement(**valid_kwargs())

    assert decision.allowed is True
    assert decision.reason == REASON_OK
    assert decision.current_state == STATE_PROVISIONAL_ACTIVE
    assert decision.next_state == STATE_AUTHORITATIVE_REPLACEMENT_PENDING


def test_output_is_deterministic_for_same_input():
    kwargs = valid_kwargs()

    first = can_start_authoritative_replacement(**kwargs)
    second = can_start_authoritative_replacement(**kwargs)

    assert first == second


def test_rejects_invalid_current_state():
    kwargs = valid_kwargs()
    kwargs["current_state"] = STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT

    decision = can_start_authoritative_replacement(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.next_state is None


def test_rejects_when_reconciliation_not_matched():
    kwargs = valid_kwargs()
    kwargs["reconciliation_status"] = "unmatched"

    decision = can_start_authoritative_replacement(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_RECONCILIATION_NOT_MATCHED
    assert decision.next_state is None


def test_rejects_when_position_update_is_not_safe():
    kwargs = valid_kwargs()
    kwargs["safe_for_position_update"] = False

    decision = can_start_authoritative_replacement(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_RECONCILIATION_NOT_MATCHED
    assert decision.next_state is None


def test_rejects_when_correction_is_not_required():
    kwargs = valid_kwargs()
    kwargs["correction_required"] = False

    decision = can_start_authoritative_replacement(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_CORRECTION_NOT_REQUIRED
    assert decision.next_state is None


def test_rejects_when_active_protection_is_not_verifiable():
    kwargs = valid_kwargs()
    kwargs["active_protection_verifiable"] = False

    decision = can_start_authoritative_replacement(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None

def test_rejects_when_replacement_already_started():
    kwargs = valid_kwargs()
    kwargs["replacement_not_started"] = False

    decision = can_start_authoritative_replacement(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.next_state is None


def test_rejects_when_provisional_sl_is_not_active():
    kwargs = valid_kwargs()
    kwargs["provisional_sl_active"] = False

    decision = can_start_authoritative_replacement(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None


def test_rejects_when_provisional_tp_is_not_active():
    kwargs = valid_kwargs()
    kwargs["provisional_tp_active"] = False

    decision = can_start_authoritative_replacement(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None
