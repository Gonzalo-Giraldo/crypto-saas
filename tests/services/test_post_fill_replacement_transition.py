from apps.api.app.services.risk.post_fill_protection_state import (
    AUTHORITATIVE_ACTIVE,
    CORRECTION_FAILED,
    CORRECTION_REQUIRED,
    PROTECTION_CRITICAL,
    PROVISIONAL_ACTIVE,
    TRAILING_READY,
)
from apps.api.app.services.risk.post_fill_replacement_transition import (
    AUTHORITATIVE_CREATE_CONFIRMED,
    AUTHORITATIVE_CREATE_FAILED,
    PROVISIONAL_CANCEL_CONFIRMED,
    PROVISIONAL_CANCEL_FAILED,
    REPLACEMENT_CRITICAL_FAILURE,
    TRAILING_TAKEOVER_READY,
    decide_replacement_transition,
)


def test_create_confirmed_moves_correction_required_to_authoritative_active():
    result = decide_replacement_transition(
        current_state=CORRECTION_REQUIRED,
        event=AUTHORITATIVE_CREATE_CONFIRMED,
    )

    assert result.allowed is True
    assert result.next_state == AUTHORITATIVE_ACTIVE


def test_create_failed_moves_correction_required_to_correction_failed():
    result = decide_replacement_transition(
        current_state=CORRECTION_REQUIRED,
        event=AUTHORITATIVE_CREATE_FAILED,
    )

    assert result.allowed is True
    assert result.next_state == CORRECTION_FAILED


def test_create_confirmed_requires_correction_required():
    result = decide_replacement_transition(
        current_state=PROVISIONAL_ACTIVE,
        event=AUTHORITATIVE_CREATE_CONFIRMED,
    )

    assert result.allowed is False
    assert result.reason == "event_requires_correction_required"


def test_provisional_cancel_confirmed_after_authoritative_active_moves_trailing_ready():
    result = decide_replacement_transition(
        current_state=AUTHORITATIVE_ACTIVE,
        event=PROVISIONAL_CANCEL_CONFIRMED,
    )

    assert result.allowed is True
    assert result.next_state == TRAILING_READY


def test_provisional_cancel_failed_keeps_authoritative_active():
    result = decide_replacement_transition(
        current_state=AUTHORITATIVE_ACTIVE,
        event=PROVISIONAL_CANCEL_FAILED,
    )

    assert result.allowed is False
    assert result.next_state == AUTHORITATIVE_ACTIVE


def test_trailing_takeover_ready_moves_authoritative_active_to_trailing_ready():
    result = decide_replacement_transition(
        current_state=AUTHORITATIVE_ACTIVE,
        event=TRAILING_TAKEOVER_READY,
    )

    assert result.allowed is True
    assert result.next_state == TRAILING_READY


def test_replacement_critical_failure_goes_critical():
    result = decide_replacement_transition(
        current_state=AUTHORITATIVE_ACTIVE,
        event=REPLACEMENT_CRITICAL_FAILURE,
    )

    assert result.allowed is True
    assert result.next_state == PROTECTION_CRITICAL


def test_unknown_event_blocked():
    result = decide_replacement_transition(
        current_state=CORRECTION_REQUIRED,
        event="UNKNOWN",
    )

    assert result.allowed is False
    assert result.reason == "unknown_replacement_event"


def test_missing_event_blocked():
    result = decide_replacement_transition(
        current_state=CORRECTION_REQUIRED,
        event="",
    )

    assert result.allowed is False
    assert result.reason == "event_required"
