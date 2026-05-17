from apps.api.app.data_runtime.models.autopick_observation_snapshot import (
    AutopickObservationSnapshot,
)
from apps.api.app.data_runtime.session import DataBase
from apps.api.app.db.session import Base


def test_autopick_observation_snapshot_model_belongs_to_data_metadata_only():
    assert AutopickObservationSnapshot.metadata is DataBase.metadata
    assert AutopickObservationSnapshot.metadata is not Base.metadata
    assert "autopick_observation_snapshots" in DataBase.metadata.tables
    assert "autopick_observation_snapshots" not in Base.metadata.tables


def test_autopick_observation_snapshot_columns_are_minimal_and_observational():
    table = AutopickObservationSnapshot.__table__
    columns = set(table.columns.keys())

    assert columns == {
        "id",
        "snapshot_id",
        "snapshot_hash",
        "broker",
        "market",
        "decision_status",
        "selected_symbol",
        "selected_rank",
        "ranked_count",
        "partial_failure_count",
        "rejected_candidates_json",
        "created_at",
    }


def test_autopick_observation_snapshot_has_expected_indexes():
    table = AutopickObservationSnapshot.__table__
    index_names = {index.name for index in table.indexes}

    assert "ix_data_autopick_snapshot_hash" in index_names
    assert "ix_data_autopick_created_at" in index_names
    assert "ix_data_autopick_selected_symbol" in index_names
    assert "ix_data_autopick_decision_status" in index_names
