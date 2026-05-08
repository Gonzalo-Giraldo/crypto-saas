from apps.api.app.services.risk.can_retry_cleanup import (
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_STALE_PROVISIONAL_PRESENT,
    can_retry_cleanup,
)
from apps.api.app.services.risk.protection_reasons import (
    REASON_INVALID_CURRENT_STATE,
    REASON_OK,
)


def test_allows_retry_cleanup_when_protection_verifiable():
    result = can_retry_cleanup(
        current_state=STATE_STALE_PROVISIONAL_PRESENT,
        protection_active_verifiable=True,
    )

    assert result.allowed is True
    assert result.reason == REASON_OK
    assert result.next_state == STATE_PROVISIONAL_CLEANUP_PENDING


def test_blocks_retry_cleanup_invalid_state():
    result = can_retry_cleanup(
        current_state="",
        protection_active_verifiable=True,
    )

    assert result.allowed is False
    assert result.reason == REASON_INVALID_CURRENT_STATE
    assert result.next_state is None


def test_blocks_retry_cleanup_when_protection_not_verifiable():
    result = can_retry_cleanup(
        current_state=STATE_STALE_PROVISIONAL_PRESENT,
        protection_active_verifiable=False,
    )

    assert result.allowed is False
    assert result.reason == "protection_not_verifiable"
    assert result.next_state is None


def test_retry_cleanup_is_deterministic():
    kwargs = dict(
        current_state=STATE_STALE_PROVISIONAL_PRESENT,
        protection_active_verifiable=True,
    )

    first = can_retry_cleanup(**kwargs)
    second = can_retry_cleanup(**kwargs)

    assert first == second
