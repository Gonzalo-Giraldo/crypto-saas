from apps.api.app.data_runtime.session import DataBase, DataSessionLocal, data_engine
from apps.api.app.db.session import Base, SessionLocal, engine


def test_data_runtime_uses_independent_metadata():
    assert DataBase is not Base
    assert DataBase.metadata is not Base.metadata


def test_data_runtime_uses_independent_engine_and_session():
    assert data_engine is not engine
    assert DataSessionLocal is not SessionLocal
    assert DataSessionLocal.kw["bind"] is data_engine
    assert SessionLocal.kw["bind"] is engine


def test_data_runtime_starts_empty():
    data_tables = set(DataBase.metadata.tables.keys())

    assert data_tables == set()
