from sqlalchemy import Column, DateTime, Float, String, func

from apps.api.app.db.session import Base


class UserRiskSettings(Base):
    __tablename__ = "user_risk_settings"

    user_id = Column(String, primary_key=True, index=True)
    capital_base_usd = Column(Float, nullable=False, default=10000.0)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
