from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, func

from apps.api.app.db.session import Base


class RiskProfileConfig(Base):
    __tablename__ = "risk_profile_config"

    profile_name = Column(String, primary_key=True, index=True)
    max_risk_per_trade_pct = Column(Float, nullable=False)
    max_daily_loss_pct = Column(Float, nullable=False)
    max_trades_per_day = Column(Integer, nullable=False)
    max_open_positions = Column(Integer, nullable=False)
    cooldown_between_trades_minutes = Column(Float, nullable=False)
    max_leverage = Column(Float, nullable=False, default=1.0)
    stop_loss_required = Column(Boolean, nullable=False, default=True)
    min_rr = Column(Float, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
