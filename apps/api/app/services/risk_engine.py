from sqlalchemy import select
from apps.api.app.models.daily_risk import DailyRiskState
from apps.api.app.core.time import today_colombia


def get_or_create_daily_state(db, user_id):
    today = today_colombia()

    dr = (
        db.execute(
            select(DailyRiskState).where(
                DailyRiskState.user_id == user_id,
                DailyRiskState.day == today,
            )
        )
        .scalar_one_or_none()
    )

    if not dr:
        dr = DailyRiskState(
            user_id=user_id,
            day=today,
            trades_today=0,
            realized_pnl_today=0.0,
            daily_stop=-5.0,
            max_trades=3,
        )
        db.add(dr)
        db.commit()
        db.refresh(dr)

    return dr


def check_risk_before_open(dr):
    if dr.realized_pnl_today <= dr.daily_stop:
        return "Risk block: daily stop reached"

    if dr.trades_today >= dr.max_trades:
        return "Risk block: max trades reached"

    return None


def update_after_close(dr, realized_pnl):
    dr.realized_pnl_today += realized_pnl
    dr.trades_today += 1
