from apps.api.app.data_runtime.models.autopick_observation_snapshot import (
    AutopickObservationExport,
)
from apps.api.app.data_runtime.session import DataBase
from apps.api.app.db.session import Base


def test_autopick_export_model_belongs_to_data_metadata_only():
    assert AutopickObservationExport.metadata is DataBase.metadata
    assert AutopickObservationExport.metadata is not Base.metadata
    assert "autopick_observation_exports" in DataBase.metadata.tables
    assert "autopick_observation_exports" not in Base.metadata.tables


def test_autopick_export_columns_are_operational_and_auditable():
    table = AutopickObservationExport.__table__

    assert set(table.columns.keys()) == {
        "id",
        "export_id",
        "from_created_at",
        "to_created_at",
        "snapshot_count",
        "candidate_count",
        "destination_kind",
        "destination_path_or_uri",
        "checksum",
        "status",
        "started_at",
        "finished_at",
        "purged_at",
        "error_message",
    }
