from apps.api.app.services.risk.evaluate_protection_critical import (
    STATE_PROTECTION_CRITICAL,
    evaluate_protection_critical,
)
from apps.api.app.services.risk.protection_reasons import (
    REASON_OK,
    REASON_PROTECTION_NOT_VERIFIABLE,
)


def test_allows_when_protection_is_verifiable():
    result = evaluate_protection_critical(
        current_state="AUTHORITATIVE_ACTIVE",
        protection_active_verifiable=True,
    )

    assert result.allowed is True
    assert result.reason == REASON_OK
    assert result.current_state == "AUTHORITATIVE_ACTIVE"
    assert result.next_state is None


def test_returns_critical_when_protection_not_verifiable():
    result = evaluate_protection_critical(
        current_state="AUTHORITATIVE_ACTIVE",
        protection_active_verifiable=False,
    )

    assert result.allowed is False
    assert result.reason == REASON_PROTECTION_NOT_VERIFIABLE
    assert result.current_state == STATE_PROTECTION_CRITICAL
    assert result.next_state == STATE_PROTECTION_CRITICAL


def test_evaluation_is_deterministic():
    kwargs = dict(
        current_state="AUTHORITATIVE_ACTIVE",
        protection_active_verifiable=True,
    )

    first = evaluate_protection_critical(**kwargs)
    second = evaluate_protection_critical(**kwargs)

    assert first == second
