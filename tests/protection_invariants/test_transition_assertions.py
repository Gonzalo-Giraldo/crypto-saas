from apps.protection.constants import (
    STATE_PROVISIONAL_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_TRAILING_READY,
    REASON_INVALID_CURRENT_STATE,
)

from apps.protection.transition_assertions import (
    assert_allowed_transition,
    is_allowed_transition,
)


def test_is_allowed_transition_accepts_registered_transition():
    assert is_allowed_transition(
        current_state=STATE_PROVISIONAL_ACTIVE,
        next_state=STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    )


def test_is_allowed_transition_rejects_unregistered_transition():
    assert not is_allowed_transition(
        current_state=STATE_PROVISIONAL_ACTIVE,
        next_state=STATE_AUTHORITATIVE_ACTIVE,
    )


def test_assert_allowed_transition_returns_allowed_decision():
    decision = assert_allowed_transition(
        current_state=STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
        next_state=STATE_PROVISIONAL_CLEANUP_PENDING,
    )

    assert decision.allowed is True
    assert decision.current_state == STATE_AUTHORITATIVE_REPLACEMENT_PENDING
    assert decision.next_state == STATE_PROVISIONAL_CLEANUP_PENDING


def test_assert_allowed_transition_rejects_forbidden_decision():
    decision = assert_allowed_transition(
        current_state=STATE_PROVISIONAL_ACTIVE,
        next_state=STATE_PROVISIONAL_CLEANUP_PENDING,
    )

    assert decision.allowed is False
    assert decision.reason == REASON_INVALID_CURRENT_STATE
    assert decision.current_state == STATE_PROVISIONAL_ACTIVE
    assert decision.next_state is None


def test_trailing_ready_has_no_allowed_outbound_transition():
    assert not is_allowed_transition(
        current_state=STATE_TRAILING_READY,
        next_state=STATE_AUTHORITATIVE_ACTIVE,
    )
