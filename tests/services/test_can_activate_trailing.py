from apps.api.app.services.risk.can_activate_trailing import (
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_TRAILING_READY,
    can_activate_trailing,
)
from apps.api.app.services.risk.protection_reasons import (
    REASON_INVALID_CURRENT_STATE,
    REASON_OK,
    REASON_PROTECTION_NOT_VERIFIABLE,
)


def test_allows_trailing_from_clean_authoritative_active():
    result = can_activate_trailing(
        current_state=STATE_AUTHORITATIVE_ACTIVE,
        protection_active_verifiable=True,
    )

    assert result.allowed is True
    assert result.reason == REASON_OK
    assert result.next_state == STATE_TRAILING_READY


def test_blocks_trailing_from_cleanup_pending():
    result = can_activate_trailing(
        current_state="PROVISIONAL_CLEANUP_PENDING",
        protection_active_verifiable=True,
    )

    assert result.allowed is False
    assert result.reason == REASON_INVALID_CURRENT_STATE
    assert result.next_state is None


def test_blocks_trailing_from_stale_provisional_present():
    result = can_activate_trailing(
        current_state="STALE_PROVISIONAL_PRESENT",
        protection_active_verifiable=True,
    )

    assert result.allowed is False
    assert result.reason == REASON_INVALID_CURRENT_STATE
    assert result.next_state is None


def test_blocks_trailing_when_protection_not_verifiable():
    result = can_activate_trailing(
        current_state=STATE_AUTHORITATIVE_ACTIVE,
        protection_active_verifiable=False,
    )

    assert result.allowed is False
    assert result.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert result.next_state is None


def test_trailing_evaluation_is_deterministic():
    kwargs = dict(
        current_state=STATE_AUTHORITATIVE_ACTIVE,
        protection_active_verifiable=True,
    )

    first = can_activate_trailing(**kwargs)
    second = can_activate_trailing(**kwargs)

    assert first == second
