from apps.worker.app.engine.binance_protection_creation_gate import (
    evaluate_protection_creation_gate,
)


def test_blocks_when_already_protected():
    result = evaluate_protection_creation_gate(protection_state="PROTECTED")
    assert result["allow_creation"] is False
    assert result["reason"] == "already_protected"


def test_blocks_when_partially_protected():
    result = evaluate_protection_creation_gate(protection_state="PARTIALLY_PROTECTED")
    assert result["allow_creation"] is False
    assert result["reason"] == "partial_protection_detected"


def test_blocks_when_unknown():
    result = evaluate_protection_creation_gate(protection_state="PROTECTION_UNKNOWN")
    assert result["allow_creation"] is False
    assert result["reason"] == "protection_state_unknown"


def test_blocks_when_triggered():
    result = evaluate_protection_creation_gate(protection_state="TRIGGERED")
    assert result["allow_creation"] is False
    assert result["reason"] == "triggered_requires_position_reconciliation"


def test_allows_when_unprotected():
    result = evaluate_protection_creation_gate(protection_state="UNPROTECTED")
    assert result["allow_creation"] is True
    assert result["reason"] == "eligible_for_creation"


def test_allows_when_expired():
    result = evaluate_protection_creation_gate(protection_state="EXPIRED")
    assert result["allow_creation"] is True
    assert result["reason"] == "eligible_for_creation"
