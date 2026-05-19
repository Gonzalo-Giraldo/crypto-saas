from apps.api.app.data_runtime.models.autopick_observation_snapshot import (
    AutopickObservationSnapshot,
)
from apps.api.app.data_runtime.session import DataBase, get_data_engine, get_data_session_local
from apps.api.app.db.session import Base, SessionLocal, engine


def test_data_runtime_uses_independent_metadata():
    assert DataBase is not Base
    assert DataBase.metadata is not Base.metadata


def test_data_runtime_uses_independent_engine_and_session(monkeypatch):
    monkeypatch.setattr(
        "apps.api.app.data_runtime.config.settings.DATA_DATABASE_URL",
        "sqlite://",
    )

    data_engine = get_data_engine()
    data_session_local = get_data_session_local()

    assert data_engine is not engine
    assert data_session_local is not SessionLocal
    assert data_session_local.kw["bind"] is data_engine
    assert SessionLocal.kw["bind"] is engine


def test_data_runtime_contains_only_data_plane_tables():
    data_tables = set(DataBase.metadata.tables.keys())

    assert data_tables == {
        "autopick_observation_snapshots",
        "autopick_observation_candidates",
        "autopick_observation_exports",
    }
    assert AutopickObservationSnapshot.__table__.metadata is DataBase.metadata
    assert "autopick_observation_snapshots" not in Base.metadata.tables
