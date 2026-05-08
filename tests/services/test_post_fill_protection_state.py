from apps.api.app.services.risk.post_fill_protection_state import (
    AUTHORITATIVE_ACTIVE,
    AUTHORITATIVE_READY,
    CORRECTION_FAILED,
    CORRECTION_NOT_REQUIRED,
    CORRECTION_REQUIRED,
    PROTECTION_CRITICAL,
    PROVISIONAL_ACTIVE,
    PROVISIONAL_PENDING,
    TRAILING_ACTIVE,
    TRAILING_READY,
    can_transition_protection_state,
)


def test_provisional_pending_to_active_allowed():
    result = can_transition_protection_state(
        current_state=PROVISIONAL_PENDING,
        next_state=PROVISIONAL_ACTIVE,
    )

    assert result.allowed is True
    assert result.reason == "ok"


def test_provisional_active_to_authoritative_ready_allowed():
    result = can_transition_protection_state(
        current_state=PROVISIONAL_ACTIVE,
        next_state=AUTHORITATIVE_READY,
    )

    assert result.allowed is True


def test_authoritative_ready_to_correction_required_allowed():
    result = can_transition_protection_state(
        current_state=AUTHORITATIVE_READY,
        next_state=CORRECTION_REQUIRED,
    )

    assert result.allowed is True


def test_authoritative_ready_to_correction_not_required_allowed():
    result = can_transition_protection_state(
        current_state=AUTHORITATIVE_READY,
        next_state=CORRECTION_NOT_REQUIRED,
    )

    assert result.allowed is True


def test_correction_required_to_authoritative_active_allowed():
    result = can_transition_protection_state(
        current_state=CORRECTION_REQUIRED,
        next_state=AUTHORITATIVE_ACTIVE,
    )

    assert result.allowed is True


def test_correction_required_to_failed_allowed():
    result = can_transition_protection_state(
        current_state=CORRECTION_REQUIRED,
        next_state=CORRECTION_FAILED,
    )

    assert result.allowed is True


def test_authoritative_active_to_trailing_ready_allowed():
    result = can_transition_protection_state(
        current_state=AUTHORITATIVE_ACTIVE,
        next_state=TRAILING_READY,
    )

    assert result.allowed is True


def test_trailing_ready_to_trailing_active_allowed():
    result = can_transition_protection_state(
        current_state=TRAILING_READY,
        next_state=TRAILING_ACTIVE,
    )

    assert result.allowed is True


def test_any_state_can_go_critical():
    for state in [
        PROVISIONAL_PENDING,
        PROVISIONAL_ACTIVE,
        AUTHORITATIVE_READY,
        CORRECTION_NOT_REQUIRED,
        CORRECTION_REQUIRED,
        AUTHORITATIVE_ACTIVE,
        CORRECTION_FAILED,
        TRAILING_READY,
        TRAILING_ACTIVE,
    ]:
        result = can_transition_protection_state(
            current_state=state,
            next_state=PROTECTION_CRITICAL,
        )

        assert result.allowed is True


def test_invalid_transition_blocked():
    result = can_transition_protection_state(
        current_state=PROVISIONAL_PENDING,
        next_state=TRAILING_ACTIVE,
    )

    assert result.allowed is False
    assert result.reason == "transition_not_allowed"


def test_missing_current_state_blocked():
    result = can_transition_protection_state(
        current_state="",
        next_state=PROVISIONAL_ACTIVE,
    )

    assert result.allowed is False
    assert result.reason == "current_state_required"


def test_missing_next_state_blocked():
    result = can_transition_protection_state(
        current_state=PROVISIONAL_PENDING,
        next_state="",
    )

    assert result.allowed is False
    assert result.reason == "next_state_required"
