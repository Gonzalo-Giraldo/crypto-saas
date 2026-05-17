from apps.api.app.data_runtime.services.autopick_export_service import (
    validate_export_transition,
)


def test_export_transition_allows_pending_to_exporting():
    assert validate_export_transition("PENDING", "EXPORTING") is True


def test_export_transition_rejects_pending_to_purged():
    assert validate_export_transition("PENDING", "PURGED") is False


def test_export_transition_rejects_failed_to_purged():
    assert validate_export_transition("FAILED", "PURGED") is False


def test_export_transition_rejects_purged_to_anything():
    assert validate_export_transition("PURGED", "FAILED") is False


def test_invalid_export_transition_raises_fail_closed():
    from apps.api.app.data_runtime.services.autopick_export_service import (
        apply_export_transition,
    )

    class Row:
        status = "PENDING"

    try:
        apply_export_transition(Row(), "PURGED")
    except ValueError as exc:
        assert "invalid_export_transition" in str(exc)
        return

    raise AssertionError("invalid transition must fail closed")
