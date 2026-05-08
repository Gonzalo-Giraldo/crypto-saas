from apps.protection.constants import (
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_STALE_PROVISIONAL_PRESENT,
    REASON_OK,
    REASON_INVALID_CURRENT_STATE,
    REASON_PROTECTION_NOT_VERIFIABLE,
)

from apps.protection.cleanup_result_evaluator import evaluate_cleanup_result


def valid_kwargs():
    return dict(
        current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
        cleanup_successful=True,
        stale_provisional_present=False,
        authoritative_sl_active=True,
        authoritative_tp_active=True,
        active_protection_verifiable=True,
    )


def test_cleanup_success_promotes_to_authoritative_active():
    decision = evaluate_cleanup_result(**valid_kwargs())

    assert decision.allowed is True
    assert decision.reason == REASON_OK
    assert decision.current_state == STATE_PROVISIONAL_CLEANUP_PENDING
    assert decision.next_state == STATE_AUTHORITATIVE_ACTIVE


def test_cleanup_failure_with_stale_provisional_moves_to_stale_present():
    kwargs = valid_kwargs()
    kwargs["cleanup_successful"] = False
    kwargs["stale_provisional_present"] = True

    decision = evaluate_cleanup_result(**kwargs)

    assert decision.allowed is True
    assert decision.reason == REASON_OK
    assert decision.current_state == STATE_PROVISIONAL_CLEANUP_PENDING
    assert decision.next_state == STATE_STALE_PROVISIONAL_PRESENT


def test_output_is_deterministic_for_same_input():
    kwargs = valid_kwargs()

    first = evaluate_cleanup_result(**kwargs)
    second = evaluate_cleanup_result(**kwargs)

    assert first == second


def test_rejects_invalid_current_state():
    kwargs = valid_kwargs()
    kwargs["current_state"] = STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT

    decision = evaluate_cleanup_result(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.next_state is None


def test_rejects_cleanup_success_with_stale_provisional_present():
    kwargs = valid_kwargs()
    kwargs["cleanup_successful"] = True
    kwargs["stale_provisional_present"] = True

    decision = evaluate_cleanup_result(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.next_state is None


def test_rejects_cleanup_failure_without_stale_provisional_present():
    kwargs = valid_kwargs()
    kwargs["cleanup_successful"] = False
    kwargs["stale_provisional_present"] = False

    decision = evaluate_cleanup_result(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.next_state is None


def test_rejects_when_authoritative_sl_is_not_active():
    kwargs = valid_kwargs()
    kwargs["authoritative_sl_active"] = False

    decision = evaluate_cleanup_result(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None


def test_rejects_when_authoritative_tp_is_not_active():
    kwargs = valid_kwargs()
    kwargs["authoritative_tp_active"] = False

    decision = evaluate_cleanup_result(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None


def test_rejects_when_active_protection_is_not_verifiable():
    kwargs = valid_kwargs()
    kwargs["active_protection_verifiable"] = False

    decision = evaluate_cleanup_result(**kwargs)

    assert decision.allowed is False
    assert decision.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert decision.next_state is None
