import uuid
from sqlalchemy import Column, String, Boolean
from apps.api.app.db.session import Base


class User(Base):
    __tablename__ = "users"

    # Evita errores si el módulo se recarga y la tabla ya existe en Base.metadata
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

