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


def test_equivalent_path_is_registered():
    assert (
        STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT
        in ALLOWED_TRANSITIONS[STATE_PROVISIONAL_ACTIVE]
    )


def test_replacement_path_is_registered():
    assert (
        STATE_AUTHORITATIVE_REPLACEMENT_PENDING
        in ALLOWED_TRANSITIONS[STATE_PROVISIONAL_ACTIVE]
    )


def test_cleanup_transition_is_registered():
    assert (
        STATE_PROVISIONAL_CLEANUP_PENDING
        in ALLOWED_TRANSITIONS[
            STATE_AUTHORITATIVE_REPLACEMENT_PENDING
        ]
    )


def test_cleanup_success_transition_is_registered():
    assert (
        STATE_AUTHORITATIVE_ACTIVE
        in ALLOWED_TRANSITIONS[
            STATE_PROVISIONAL_CLEANUP_PENDING
        ]
    )


def test_cleanup_failure_transition_is_registered():
    assert (
        STATE_STALE_PROVISIONAL_PRESENT
        in ALLOWED_TRANSITIONS[
            STATE_PROVISIONAL_CLEANUP_PENDING
        ]
    )


def test_retry_transition_is_registered():
    assert (
        STATE_PROVISIONAL_CLEANUP_PENDING
        in ALLOWED_TRANSITIONS[
            STATE_STALE_PROVISIONAL_PRESENT
        ]
    )


def test_trailing_transition_from_authoritative_is_registered():
    assert (
        STATE_TRAILING_READY
        in ALLOWED_TRANSITIONS[
            STATE_AUTHORITATIVE_ACTIVE
        ]
    )


def test_trailing_transition_from_equivalent_is_registered():
    assert (
        STATE_TRAILING_READY
        in ALLOWED_TRANSITIONS[
            STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT
        ]
    )


def test_trailing_ready_has_no_outbound_transitions():
    assert ALLOWED_TRANSITIONS[STATE_TRAILING_READY] == set()


def test_equivalent_path_is_isolated():
    assert (
        STATE_AUTHORITATIVE_REPLACEMENT_PENDING
        not in ALLOWED_TRANSITIONS[
            STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT
        ]
    )


def test_replacement_path_never_reaches_equivalent():
    assert (
        STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT
        not in ALLOWED_TRANSITIONS[
            STATE_AUTHORITATIVE_REPLACEMENT_PENDING
        ]
    )


def test_no_direct_transition_to_authoritative_active():
    assert (
        STATE_AUTHORITATIVE_ACTIVE
        not in ALLOWED_TRANSITIONS[
            STATE_PROVISIONAL_ACTIVE
        ]
    )


def test_no_direct_transition_to_cleanup_pending():
    assert (
        STATE_PROVISIONAL_CLEANUP_PENDING
        not in ALLOWED_TRANSITIONS[
            STATE_PROVISIONAL_ACTIVE
        ]
    )
