from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from apps.api.app.data_runtime.config import get_data_database_url


DataBase = declarative_base()

_data_engine = None
_DataSessionLocal = None


def get_data_engine():
    global _data_engine

    if _data_engine is None:
        data_database_url = get_data_database_url()

        _data_engine = create_engine(
            data_database_url,
            pool_pre_ping=True,
            connect_args={
                "check_same_thread": False
            } if data_database_url.startswith("sqlite") else {},
        )

    return _data_engine


def get_data_session_local():
    global _DataSessionLocal

    if _DataSessionLocal is None:
        _DataSessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_data_engine(),
        )

    return _DataSessionLocal


def get_data_db():
    db = get_data_session_local()()

    try:
        yield db
    finally:
        db.close()
