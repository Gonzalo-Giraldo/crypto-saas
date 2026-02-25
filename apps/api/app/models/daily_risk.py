import uuid
from sqlalchemy import Column, String, Float, Integer, Date, UniqueConstraint
from apps.api.app.db.session import Base


class DailyRiskState(Base):
    __tablename__ = "daily_risk_state"

    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_user_day"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)

    # YYYY-MM-DD (America/Bogota)
    day = Column(Date, nullable=False, index=True)

    trades_today = Column(Integer, nullable=False, default=0)
    realized_pnl_today = Column(Float, nullable=False, default=0.0)

    daily_stop = Column(Float, nullable=False, default=-5.0)
    max_trades = Column(Integer, nullable=False, default=3)
