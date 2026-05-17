from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from apps.api.app.data_runtime.models.autopick_observation_snapshot import (
    AutopickObservationExport,
)
from apps.api.app.data_runtime.services.autopick_export_service import (
    create_autopick_export_batch,
)
from apps.api.app.data_runtime.session import DataBase


def test_create_autopick_export_batch_creates_pending_append_only_row():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)

    DataBase.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db:
        row = create_autopick_export_batch(
            db=db,
            export_id="export-1",
            from_created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            to_created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            snapshot_count=10,
            candidate_count=50,
            destination_kind="disk",
            destination_path_or_uri="/data/autopick/export-1",
            checksum="pending",
        )

        row_id = row.id
        db.commit()

    with TestingSessionLocal() as db:
        rows = db.execute(
            select(AutopickObservationExport)
        ).scalars().all()

    assert len(rows) == 1

    stored = rows[0]

    assert stored.export_id == "export-1"
    assert stored.status == "PENDING"
    assert stored.snapshot_count == 10
    assert stored.candidate_count == 50
    assert stored.purged_at is None

    assert row_id == stored.id
