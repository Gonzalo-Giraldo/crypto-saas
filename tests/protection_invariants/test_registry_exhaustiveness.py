from apps.protection.constants import (
    STATE_PROVISIONAL_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_STALE_PROVISIONAL_PRESENT,
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_TRAILING_READY,
)

from apps.protection.transition_registry import (
    ALLOWED_TRANSITIONS,
)


ALL_LIFECYCLE_STATES = {
    STATE_PROVISIONAL_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_STALE_PROVISIONAL_PRESENT,
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_TRAILING_READY,
}


def test_registry_contains_every_lifecycle_state():
    assert set(ALLOWED_TRANSITIONS) == ALL_LIFECYCLE_STATES


def test_registry_targets_are_known_lifecycle_states():
    for next_states in ALLOWED_TRANSITIONS.values():
        assert next_states <= ALL_LIFECYCLE_STATES


def test_registry_has_no_self_transitions():
    for current_state, next_states in ALLOWED_TRANSITIONS.items():
        assert current_state not in next_states


def test_only_terminal_state_has_no_outbound_transitions():
    terminal_states = {
        state
        for state, next_states in ALLOWED_TRANSITIONS.items()
        if not next_states
    }

    assert terminal_states == {STATE_TRAILING_READY}


def test_provisional_active_has_only_equivalent_or_replacement_exit():
    assert ALLOWED_TRANSITIONS[STATE_PROVISIONAL_ACTIVE] == {
        STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
        STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    }


def test_cleanup_pending_has_only_success_or_stale_exit():
    assert ALLOWED_TRANSITIONS[STATE_PROVISIONAL_CLEANUP_PENDING] == {
        STATE_AUTHORITATIVE_ACTIVE,
        STATE_STALE_PROVISIONAL_PRESENT,
    }


def test_stale_provisional_can_only_retry_cleanup():
    assert ALLOWED_TRANSITIONS[STATE_STALE_PROVISIONAL_PRESENT] == {
        STATE_PROVISIONAL_CLEANUP_PENDING,
    }


def test_authoritative_states_can_only_activate_trailing():
    assert ALLOWED_TRANSITIONS[STATE_AUTHORITATIVE_ACTIVE] == {
        STATE_TRAILING_READY,
    }

    assert ALLOWED_TRANSITIONS[STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT] == {
        STATE_TRAILING_READY,
    }
