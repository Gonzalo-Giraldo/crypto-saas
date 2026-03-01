import uuid
from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.sql import func

from apps.api.app.db.session import Base


class RuntimeSetting(Base):
    __tablename__ = "runtime_settings"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String, nullable=False, unique=True, index=True)
    bool_value = Column(Boolean, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
