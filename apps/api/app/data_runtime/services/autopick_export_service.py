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
