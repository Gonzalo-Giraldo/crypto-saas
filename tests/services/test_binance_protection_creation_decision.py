from apps.worker.app.engine.binance_protection_creation_decision import (
    decide_protection_creation,
)


def test_allows_creation_when_gate_allows():
    result = decide_protection_creation(
        allow_creation=True,
        protection_state="UNPROTECTED",
        reason="eligible_for_creation",
    )

    assert result["proceed"] is True
    assert result["freeze_runtime"] is False


def test_blocks_and_freezes_when_unknown():
    result = decide_protection_creation(
        allow_creation=False,
        protection_state="PROTECTION_UNKNOWN",
        reason="protection_state_unknown",
    )

    assert result["proceed"] is False
    assert result["freeze_runtime"] is True


def test_blocks_and_freezes_when_partially_protected():
    result = decide_protection_creation(
        allow_creation=False,
        protection_state="PARTIALLY_PROTECTED",
        reason="partial_protection_detected",
    )

    assert result["proceed"] is False
    assert result["freeze_runtime"] is True


def test_blocks_triggered_reconciliation():
    result = decide_protection_creation(
        allow_creation=False,
        protection_state="TRIGGERED",
        reason="triggered_requires_position_reconciliation",
    )

    assert result["proceed"] is False
    assert result["freeze_runtime"] is True
