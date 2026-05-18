from apps.api.app.services.runtime_scheduler.runtime_session_reconciliation import (
    evaluate_runtime_generation_reconciliation,
)


def test_runtime_generation_reconciliation_matches_equal_generations():
    result = evaluate_runtime_generation_reconciliation(
        local_runtime_generation=3,
        durable_runtime_generation=3,
    )

    assert result.matches is True
    assert result.reason is None


def test_runtime_generation_reconciliation_fails_closed_without_local_generation():
    result = evaluate_runtime_generation_reconciliation(
        local_runtime_generation=None,
        durable_runtime_generation=3,
    )

    assert result.matches is False
    assert result.reason == "local_runtime_generation_missing"


def test_runtime_generation_reconciliation_fails_closed_without_durable_generation():
    result = evaluate_runtime_generation_reconciliation(
        local_runtime_generation=3,
        durable_runtime_generation=None,
    )

    assert result.matches is False
    assert result.reason == "durable_runtime_generation_missing"


def test_runtime_generation_reconciliation_fails_closed_on_mismatch():
    result = evaluate_runtime_generation_reconciliation(
        local_runtime_generation=2,
        durable_runtime_generation=3,
    )

    assert result.matches is False
    assert result.reason == "runtime_generation_mismatch"


def test_runtime_generation_reconciliation_fails_closed_on_invalid_local_generation():
    result = evaluate_runtime_generation_reconciliation(
        local_runtime_generation=0,
        durable_runtime_generation=3,
    )

    assert result.matches is False
    assert result.reason == "local_runtime_generation_invalid"


def test_runtime_generation_reconciliation_fails_closed_on_invalid_durable_generation():
    result = evaluate_runtime_generation_reconciliation(
        local_runtime_generation=3,
        durable_runtime_generation=0,
    )

    assert result.matches is False
    assert result.reason == "durable_runtime_generation_invalid"
