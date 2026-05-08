from apps.protection.constants import (
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_ACTIVE,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_STALE_PROVISIONAL_PRESENT,
    STATE_TRAILING_READY,
    REASON_OK,
    REASON_INVALID_CURRENT_STATE,
    REASON_AUTHORITATIVE_NOT_STABLE,
    REASON_PROTECTION_NOT_VERIFIABLE,
)

from apps.protection.trailing_evaluator import can_activate_trailing


def valid_kwargs():
    return dict(
        current_state=STATE_AUTHORITATIVE_ACTIVE,
        baseline_stable=True,
        active_protection_verifiable=True,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        trailing_not_active=True,
    )


def test_activates_trailing_from_authoritative_active():
    decision = can_activate_trailing(**valid_kwargs())

    assert decision.allowed is True
    assert decision.reason == REASON_OK
    assert decision.current_state == STATE_AUTHORITATIVE_ACTIVE
    assert decision.next_state == STATE_TRAILING_READY


def test_activates_trailing_from_authoritative_active_equivalent():
    kwargs = valid_kwargs()
    kwargs["current_state"] = STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT

    decision = can_activate_trailing(**kwargs)

    assert decision.allowed is True
    assert decision.reason == REASON_OK
    assert decision.current_state == STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT
    assert decision.next_state == STATE_TRAILING_READY


def test_output_is_deterministic_for_same_input():
    kwargs = valid_kwargs()

    first = can_activate_trailing(**kwargs)
    second = can_activate_trailing(**kwargs)

    assert first == second


def test_rejects_when_baseline_is_not_stable():
    kwargs = valid_kwargs()
    kwargs["baseline_stable"] = False

    decision = can_activate_trailing(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_AUTHORITATIVE_NOT_STABLE
    assert decision.next_state is None


def test_rejects_when_authoritative_sl_is_not_active():
    kwargs = valid_kwargs()
    kwargs["authoritative_sl_active"] = False

    decision = can_activate_trailing(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None


def test_rejects_when_authoritative_tp_is_not_active():
    kwargs = valid_kwargs()
    kwargs["authoritative_tp_active"] = False

    decision = can_activate_trailing(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None


def test_rejects_when_active_protection_is_not_verifiable():
    kwargs = valid_kwargs()
    kwargs["active_protection_verifiable"] = False

    decision = can_activate_trailing(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None


def test_rejects_when_trailing_is_already_active():
    kwargs = valid_kwargs()
    kwargs["trailing_not_active"] = False

    decision = can_activate_trailing(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.next_state is None


def test_rejects_from_provisional_active():
    kwargs = valid_kwargs()
    kwargs["current_state"] = STATE_PROVISIONAL_ACTIVE

    decision = can_activate_trailing(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.next_state is None


def test_rejects_from_authoritative_replacement_pending():
    kwargs = valid_kwargs()
    kwargs["current_state"] = STATE_AUTHORITATIVE_REPLACEMENT_PENDING

    decision = can_activate_trailing(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.next_state is None


def test_rejects_from_provisional_cleanup_pending():
    kwargs = valid_kwargs()
    kwargs["current_state"] = STATE_PROVISIONAL_CLEANUP_PENDING

    decision = can_activate_trailing(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.next_state is None


def test_rejects_from_stale_provisional_present():
    kwargs = valid_kwargs()
    kwargs["current_state"] = STATE_STALE_PROVISIONAL_PRESENT

    decision = can_activate_trailing(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.next_state is None
