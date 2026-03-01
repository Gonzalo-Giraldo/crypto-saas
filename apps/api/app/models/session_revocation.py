from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func

from apps.api.app.db.session import Base


class SessionRevocation(Base):
    __tablename__ = "session_revocation"

    user_id = Column(String, primary_key=True, index=True)
    revoked_after = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

