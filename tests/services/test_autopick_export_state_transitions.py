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


def test_failed_transition_requires_error_message():
    from apps.api.app.data_runtime.services.autopick_export_service import (
        apply_export_transition,
    )

    class Row:
        status = "EXPORTING"
        error_message = None

    try:
        apply_export_transition(Row(), "FAILED")
    except ValueError as exc:
        assert "export_failure_requires_error_message" in str(exc)
        return

    raise AssertionError("FAILED transition must require error_message")


def test_verified_transition_requires_checksum():
    from apps.api.app.data_runtime.services.autopick_export_service import (
        apply_export_transition,
    )

    class Row:
        status = "EXPORTED"
        checksum = ""
        finished_at = object()
        destination_path_or_uri = "/tmp/export"
        snapshot_count = 1
        candidate_count = 0

    try:
        apply_export_transition(Row(), "VERIFIED")
    except ValueError as exc:
        assert "verified_export_requires_checksum" in str(exc)
        return

    raise AssertionError("VERIFIED transition must require checksum")


def test_verified_transition_requires_finished_at():
    from apps.api.app.data_runtime.services.autopick_export_service import (
        apply_export_transition,
    )

    class Row:
        status = "EXPORTED"
        checksum = "abc123"
        finished_at = None
        destination_path_or_uri = "/tmp/export"
        snapshot_count = 1
        candidate_count = 0

    try:
        apply_export_transition(Row(), "VERIFIED")
    except ValueError as exc:
        assert "verified_export_requires_finished_at" in str(exc)
        return

    raise AssertionError("VERIFIED transition must require finished_at")


def test_verified_transition_requires_destination():
    from apps.api.app.data_runtime.services.autopick_export_service import (
        apply_export_transition,
    )

    class Row:
        status = "EXPORTED"
        checksum = "abc123"
        finished_at = object()
        destination_path_or_uri = ""
        snapshot_count = 1
        candidate_count = 0

    try:
        apply_export_transition(Row(), "VERIFIED")
    except ValueError as exc:
        assert "verified_export_requires_destination" in str(exc)
        return

    raise AssertionError("VERIFIED transition must require destination")


def test_verified_transition_requires_exported_rows():
    from apps.api.app.data_runtime.services.autopick_export_service import (
        apply_export_transition,
    )

    class Row:
        status = "EXPORTED"
        checksum = "abc123"
        finished_at = object()
        destination_path_or_uri = "/tmp/export"
        snapshot_count = 0
        candidate_count = 0

    try:
        apply_export_transition(Row(), "VERIFIED")
    except ValueError as exc:
        assert "verified_export_requires_rows" in str(exc)
        return

    raise AssertionError("VERIFIED transition must require exported rows")
