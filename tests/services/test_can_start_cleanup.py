from apps.api.app.services.risk.can_start_cleanup import (
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    can_start_cleanup,
)
from apps.api.app.services.risk.protection_reasons import (
    REASON_INVALID_CURRENT_STATE,
    REASON_OK,
)


def test_allows_cleanup_when_authoritative_stable():
    result = can_start_cleanup(
        current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
        authoritative_protection_stable=True,
    )

    assert result.allowed is True
    assert result.reason == REASON_OK
    assert result.next_state == STATE_AUTHORITATIVE_ACTIVE


def test_blocks_cleanup_invalid_state():
    result = can_start_cleanup(
        current_state="",
        authoritative_protection_stable=True,
    )

    assert result.allowed is False
    assert result.reason == REASON_INVALID_CURRENT_STATE
    assert result.next_state is None


def test_blocks_cleanup_when_authoritative_not_stable():
    result = can_start_cleanup(
        current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
        authoritative_protection_stable=False,
    )

    assert result.allowed is False
    assert result.reason == "authoritative_not_stable"
    assert result.next_state is None


def test_cleanup_evaluation_is_deterministic():
    kwargs = dict(
        current_state=STATE_PROVISIONAL_CLEANUP_PENDING,
        authoritative_protection_stable=True,
    )

    first = can_start_cleanup(**kwargs)
    second = can_start_cleanup(**kwargs)

    assert first == second
