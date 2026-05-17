from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from apps.api.app.data_runtime.config import get_data_database_url


DATA_DATABASE_URL = get_data_database_url()

data_engine = create_engine(
    DATA_DATABASE_URL,
    pool_pre_ping=True,
    connect_args={
        "check_same_thread": False
    } if DATA_DATABASE_URL.startswith("sqlite") else {},
)

DataSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=data_engine,
)

DataBase = declarative_base()


def get_data_db():
    db = DataSessionLocal()
    try:
        yield db
    finally:
        db.close()
