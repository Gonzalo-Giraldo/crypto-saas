from apps.protection.constants import (
    STATE_PROVISIONAL_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    REASON_EQUIVALENT_ACCEPTED,
    REASON_INVALID_CURRENT_STATE,
    REASON_RECONCILIATION_NOT_MATCHED,
    REASON_CORRECTION_REQUIRED,
    REASON_PROTECTION_NOT_VERIFIABLE,
)

from apps.protection.equivalent_evaluator import can_accept_authoritative_equivalent


def valid_kwargs():
    return dict(
        current_state=STATE_PROVISIONAL_ACTIVE,
        reconciliation_status="matched",
        safe_for_position_update=True,
        correction_required=False,
        provisional_sl_active=True,
        provisional_tp_active=True,
        active_protection_verifiable=True,
        replacement_not_started=True,
    )


def test_accepts_authoritative_equivalent_when_all_evidence_is_valid():
    decision = can_accept_authoritative_equivalent(**valid_kwargs())

    assert decision.allowed is True
    assert decision.reason == REASON_EQUIVALENT_ACCEPTED
    assert decision.current_state == STATE_PROVISIONAL_ACTIVE
    assert decision.next_state == STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT


def test_output_is_deterministic_for_same_input():
    kwargs = valid_kwargs()

    first = can_accept_authoritative_equivalent(**kwargs)
    second = can_accept_authoritative_equivalent(**kwargs)

    assert first == second


def test_rejects_invalid_current_state():
    kwargs = valid_kwargs()
    kwargs["current_state"] = STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT

    decision = can_accept_authoritative_equivalent(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.next_state is None


def test_rejects_when_reconciliation_not_matched():
    kwargs = valid_kwargs()
    kwargs["reconciliation_status"] = "unmatched"

    decision = can_accept_authoritative_equivalent(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_RECONCILIATION_NOT_MATCHED
    assert decision.next_state is None


def test_rejects_when_position_update_is_not_safe():
    kwargs = valid_kwargs()
    kwargs["safe_for_position_update"] = False

    decision = can_accept_authoritative_equivalent(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_RECONCILIATION_NOT_MATCHED
    assert decision.next_state is None


def test_rejects_when_correction_is_required():
    kwargs = valid_kwargs()
    kwargs["correction_required"] = True

    decision = can_accept_authoritative_equivalent(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_CORRECTION_REQUIRED
    assert decision.next_state is None


def test_rejects_when_active_protection_is_not_verifiable():
    kwargs = valid_kwargs()
    kwargs["active_protection_verifiable"] = False

    decision = can_accept_authoritative_equivalent(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None


def test_rejects_when_provisional_sl_is_not_active():
    kwargs = valid_kwargs()
    kwargs["provisional_sl_active"] = False

    decision = can_accept_authoritative_equivalent(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None


def test_rejects_when_provisional_tp_is_not_active():
    kwargs = valid_kwargs()
    kwargs["provisional_tp_active"] = False

    decision = can_accept_authoritative_equivalent(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None


def test_rejects_when_replacement_already_started():
    kwargs = valid_kwargs()
    kwargs["replacement_not_started"] = False

    decision = can_accept_authoritative_equivalent(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.next_state is None
