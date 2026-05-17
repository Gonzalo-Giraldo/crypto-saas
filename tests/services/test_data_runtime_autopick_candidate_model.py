from apps.api.app.data_runtime.models.autopick_observation_snapshot import (
    AutopickObservationCandidate,
    AutopickObservationSnapshot,
)
from apps.api.app.data_runtime.session import DataBase
from apps.api.app.db.session import Base


def test_autopick_candidate_model_belongs_to_data_metadata_only():
    assert AutopickObservationCandidate.metadata is DataBase.metadata
    assert AutopickObservationCandidate.metadata is not Base.metadata
    assert "autopick_observation_candidates" in DataBase.metadata.tables
    assert "autopick_observation_candidates" not in Base.metadata.tables


def test_autopick_candidate_columns_are_observational():
    table = AutopickObservationCandidate.__table__

    assert set(table.columns.keys()) == {
        "id",
        "snapshot_id",
        "rank",
        "symbol",
        "side",
        "valid",
        "reason",
        "final_score",
        "selected",
        "entry_price_reference",
        "features_json",
        "created_at",
    }


def test_autopick_candidate_table_does_not_join_runtime_authority():
    assert "autopick_observation_snapshots" in DataBase.metadata.tables
    assert AutopickObservationSnapshot.__table__.name == "autopick_observation_snapshots"
