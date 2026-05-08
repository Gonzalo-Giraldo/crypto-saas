from apps.protection.constants import (
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    REASON_OK,
    REASON_INVALID_CURRENT_STATE,
    REASON_PROTECTION_NOT_VERIFIABLE,
)

from apps.protection.cleanup_evaluator import can_start_cleanup


def valid_kwargs():
    return dict(
        current_state=STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        active_protection_verifiable=True,
    )


def test_starts_cleanup_when_authoritative_exits_are_verified():
    decision = can_start_cleanup(**valid_kwargs())

    assert decision.allowed is True
    assert decision.reason == REASON_OK
    assert decision.current_state == STATE_AUTHORITATIVE_REPLACEMENT_PENDING
    assert decision.next_state == STATE_PROVISIONAL_CLEANUP_PENDING


def test_output_is_deterministic_for_same_input():
    kwargs = valid_kwargs()

    first = can_start_cleanup(**kwargs)
    second = can_start_cleanup(**kwargs)

    assert first == second


def test_rejects_invalid_current_state():
    kwargs = valid_kwargs()
    kwargs["current_state"] = STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT

    decision = can_start_cleanup(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.next_state is None


def test_rejects_when_authoritative_sl_is_not_active():
    kwargs = valid_kwargs()
    kwargs["authoritative_sl_active"] = False

    decision = can_start_cleanup(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None


def test_rejects_when_authoritative_tp_is_not_active():
    kwargs = valid_kwargs()
    kwargs["authoritative_tp_active"] = False

    decision = can_start_cleanup(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None


def test_rejects_when_active_protection_is_not_verifiable():
    kwargs = valid_kwargs()
    kwargs["active_protection_verifiable"] = False

    decision = can_start_cleanup(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None
