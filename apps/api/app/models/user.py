from apps.api.app.db.session import Base
from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func
import uuid


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="trader")
    password_changed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
