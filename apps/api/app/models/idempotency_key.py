import uuid
from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from apps.api.app.db.session import Base


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "endpoint", "key_hash", name="uq_idempotency_user_endpoint_key"),
        {"extend_existing": True},
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    endpoint = Column(String, nullable=False, index=True)
    key_hash = Column(String, nullable=False, index=True)
    request_hash = Column(String, nullable=False, index=True)
    response_json = Column(Text, nullable=False)
    status_code = Column(Integer, nullable=False, default=200)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
