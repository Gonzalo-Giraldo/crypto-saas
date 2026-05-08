from apps.protection.constants import (
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_STALE_PROVISIONAL_PRESENT,
    REASON_OK,
    REASON_INVALID_CURRENT_STATE,
    REASON_PROTECTION_NOT_VERIFIABLE,
)

from apps.protection.retry_cleanup_evaluator import can_retry_cleanup


def valid_kwargs():
    return dict(
        current_state=STATE_STALE_PROVISIONAL_PRESENT,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        active_protection_verifiable=True,
        stale_provisional_present=True,
        cleanup_retry_allowed=True,
    )


def test_allows_retry_cleanup_when_authoritative_protection_is_verifiable():
    decision = can_retry_cleanup(**valid_kwargs())

    assert decision.allowed is True
    assert decision.reason == REASON_OK
    assert decision.current_state == STATE_STALE_PROVISIONAL_PRESENT
    assert decision.next_state == STATE_PROVISIONAL_CLEANUP_PENDING


def test_output_is_deterministic_for_same_input():
    kwargs = valid_kwargs()

    first = can_retry_cleanup(**kwargs)
    second = can_retry_cleanup(**kwargs)

    assert first == second


def test_rejects_invalid_current_state():
    kwargs = valid_kwargs()
    kwargs["current_state"] = STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT

    decision = can_retry_cleanup(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.next_state is None


def test_rejects_when_stale_provisional_is_not_present():
    kwargs = valid_kwargs()
    kwargs["stale_provisional_present"] = False

    decision = can_retry_cleanup(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.next_state is None


def test_rejects_when_cleanup_retry_is_not_allowed():
    kwargs = valid_kwargs()
    kwargs["cleanup_retry_allowed"] = False

    decision = can_retry_cleanup(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.next_state is None


def test_rejects_when_authoritative_sl_is_not_active():
    kwargs = valid_kwargs()
    kwargs["authoritative_sl_active"] = False

    decision = can_retry_cleanup(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None


def test_rejects_when_authoritative_tp_is_not_active():
    kwargs = valid_kwargs()
    kwargs["authoritative_tp_active"] = False

    decision = can_retry_cleanup(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None


def test_rejects_when_active_protection_is_not_verifiable():
    kwargs = valid_kwargs()
    kwargs["active_protection_verifiable"] = False

    decision = can_retry_cleanup(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None
