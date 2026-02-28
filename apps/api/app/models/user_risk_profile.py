from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func

from apps.api.app.db.session import Base


class UserRiskProfileOverride(Base):
    __tablename__ = "user_risk_profile_override"

    user_id = Column(String, primary_key=True, index=True)
    profile_name = Column(String, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)
