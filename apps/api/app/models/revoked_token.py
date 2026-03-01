from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func

from apps.api.app.db.session import Base


class RevokedToken(Base):
    __tablename__ = "revoked_token"

    jti = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    token_type = Column(String, nullable=False)  # access | refresh
    revoked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)

