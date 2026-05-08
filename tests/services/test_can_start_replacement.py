from apps.api.app.services.risk.can_start_replacement import (
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_ACTIVE,
    can_start_replacement,
)
from apps.api.app.services.risk.protection_reasons import (
    REASON_CORRECTION_NOT_REQUIRED,
    REASON_INVALID_CURRENT_STATE,
    REASON_OK,
    REASON_PROTECTION_NOT_VERIFIABLE,
    REASON_RECONCILIATION_NOT_MATCHED,
)


def test_allows_replacement_happy_path():
    result = can_start_replacement(
        current_state=STATE_PROVISIONAL_ACTIVE,
        reconciliation_status="matched",
        correction_required=True,
        protection_active_verifiable=True,
    )

    assert result.allowed is True
    assert result.reason == REASON_OK
    assert result.next_state == STATE_AUTHORITATIVE_REPLACEMENT_PENDING


def test_blocks_invalid_current_state():
    result = can_start_replacement(
        current_state="",
        reconciliation_status="matched",
        correction_required=True,
        protection_active_verifiable=True,
    )

    assert result.allowed is False
    assert result.reason == REASON_INVALID_CURRENT_STATE
    assert result.next_state is None


def test_blocks_non_matched_reconciliation():
    result = can_start_replacement(
        current_state=STATE_PROVISIONAL_ACTIVE,
        reconciliation_status="partial",
        correction_required=True,
        protection_active_verifiable=True,
    )

    assert result.allowed is False
    assert result.reason == REASON_RECONCILIATION_NOT_MATCHED


def test_blocks_when_correction_not_required():
    result = can_start_replacement(
        current_state=STATE_PROVISIONAL_ACTIVE,
        reconciliation_status="matched",
        correction_required=False,
        protection_active_verifiable=True,
    )

    assert result.allowed is False
    assert result.reason == REASON_CORRECTION_NOT_REQUIRED


def test_blocks_when_protection_not_verifiable():
    result = can_start_replacement(
        current_state=STATE_PROVISIONAL_ACTIVE,
        reconciliation_status="matched",
        correction_required=True,
        protection_active_verifiable=False,
    )

    assert result.allowed is False
    assert result.reason == REASON_PROTECTION_NOT_VERIFIABLE


def test_repeated_evaluation_is_deterministic():
    kwargs = dict(
        current_state=STATE_PROVISIONAL_ACTIVE,
        reconciliation_status="matched",
        correction_required=True,
        protection_active_verifiable=True,
    )

    first = can_start_replacement(**kwargs)
    second = can_start_replacement(**kwargs)

    assert first == second
