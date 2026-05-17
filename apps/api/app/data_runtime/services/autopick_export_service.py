from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from apps.api.app.data_runtime.models.autopick_observation_snapshot import (
    AutopickObservationExport,
)


def create_autopick_export_batch(
    *,
    db: Session,
    export_id: str,
    from_created_at: datetime,
    to_created_at: datetime,
    snapshot_count: int,
    candidate_count: int,
    destination_kind: str,
    destination_path_or_uri: str,
    checksum: str,
) -> AutopickObservationExport:
    """
    Create an append-only Auto-pick export batch record.

    Data-plane only:
    - no runtime DB access
    - no purge
    - no filesystem writes
    - no broker mutation
    """

    row = AutopickObservationExport(
        export_id=str(export_id),
        from_created_at=from_created_at,
        to_created_at=to_created_at,
        snapshot_count=int(snapshot_count),
        candidate_count=int(candidate_count),
        destination_kind=str(destination_kind),
        destination_path_or_uri=str(destination_path_or_uri),
        checksum=str(checksum),
        status="PENDING",
        started_at=datetime.now(timezone.utc),
        finished_at=None,
        purged_at=None,
        error_message=None,
    )

    db.add(row)
    db.flush()

    return row


_ALLOWED_EXPORT_TRANSITIONS = {
    "PENDING": {"EXPORTING"},
    "EXPORTING": {"EXPORTED", "FAILED"},
    "EXPORTED": {"VERIFIED", "FAILED"},
    "VERIFIED": {"PURGED", "FAILED"},
    "FAILED": set(),
    "PURGED": set(),
}


def validate_export_transition(current_status: str, next_status: str) -> bool:
    current = str(current_status or "").upper().strip()
    nxt = str(next_status or "").upper().strip()

    return nxt in _ALLOWED_EXPORT_TRANSITIONS.get(current, set())


def apply_export_transition(row, next_status: str):
    current = str(getattr(row, "status", "") or "").upper().strip()
    nxt = str(next_status or "").upper().strip()

    if not validate_export_transition(current, nxt):
        raise ValueError(f"invalid_export_transition:{current}->{nxt}")

    if nxt == "FAILED" and not str(getattr(row, "error_message", "") or "").strip():
        raise ValueError("export_failure_requires_error_message")

    row.status = nxt
    return row
