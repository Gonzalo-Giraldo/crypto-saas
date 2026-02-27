from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.api.deps import get_current_user, require_role
from apps.api.app.db.session import get_db
from apps.api.app.models.audit_log import AuditLog
from apps.api.app.models.daily_risk import DailyRiskState
from apps.api.app.models.exchange_secret import ExchangeSecret
from apps.api.app.models.position import Position
from apps.api.app.models.strategy_assignment import StrategyAssignment
from apps.api.app.schemas.execution import (
    BinanceTestOrderOut,
    BinanceTestOrderRequest,
    IbkrTestOrderOut,
    IbkrTestOrderRequest,
    ExecutionPrepareOut,
    ExecutionPrepareRequest,
)
from apps.api.app.schemas.strategy import (
    PretradeCheckOut,
    PretradeCheckRequest,
    StrategyAssignmentOut,
    StrategyAssignOut,
    StrategyAssignRequest,
)
from apps.api.app.schemas.security import ReencryptSecretsOut, ReencryptSecretsRequest
from apps.api.app.models.user import User
from apps.api.app.schemas.audit import AuditOut
from apps.api.app.core.time import today_colombia
from apps.api.app.services.audit import log_audit_event
from apps.api.app.services.key_rotation import reencrypt_exchange_secrets
from apps.api.app.services.risk_profiles import resolve_risk_profile_for_email
from apps.api.app.services.strategy_assignments import (
    is_exchange_enabled_for_user,
    resolve_strategy_for_user_exchange,
    upsert_strategy_assignment,
)
from apps.worker.app.engine.execution_runtime import (
    execute_binance_test_order_for_user,
    execute_ibkr_test_order_for_user,
    prepare_execution_for_user,
)

router = APIRouter(prefix="/ops", tags=["ops"])


def _assert_exchange_enabled(
    db: Session,
    current_user: User,
    exchange: str,
):
    if is_exchange_enabled_for_user(
        db=db,
        user_id=current_user.id,
        exchange=exchange,
    ):
        return

    log_audit_event(
        db,
        action="execution.blocked.exchange_disabled",
        user_id=current_user.id,
        entity_type="execution",
        details={"exchange": exchange},
    )
    db.commit()
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Exchange {exchange} is disabled for this user",
    )


def _evaluate_pretrade_for_user(
    db: Session,
    current_user: User,
    exchange: str,
):
    strategy = resolve_strategy_for_user_exchange(
        db=db,
        user_id=current_user.id,
        exchange=exchange,
    )
    profile = resolve_risk_profile_for_email(current_user.email)
    today = today_colombia()
    checks = []

    checks.append(
        {
            "name": "strategy_enabled",
            "passed": bool(strategy["enabled"]),
            "detail": f"{strategy['strategy_id']} ({strategy['source']})",
        }
    )

    has_secret = (
        db.execute(
            select(ExchangeSecret).where(
                ExchangeSecret.user_id == current_user.id,
                ExchangeSecret.exchange == exchange,
            )
        )
        .scalar_one_or_none()
        is not None
    )
    checks.append(
        {
            "name": "exchange_secret_configured",
            "passed": has_secret,
            "detail": exchange,
        }
    )

    dr = (
        db.execute(
            select(DailyRiskState).where(
                DailyRiskState.user_id == current_user.id,
                DailyRiskState.day == today,
            )
        )
        .scalar_one_or_none()
    )
    max_trades = int(profile["max_trades_per_day"])
    daily_stop = -abs(float(profile["max_daily_loss_pct"]))
    trades_today = int(dr.trades_today) if dr else 0
    realized_pnl_today = float(dr.realized_pnl_today) if dr else 0.0

    checks.append(
        {
            "name": "daily_stop_not_reached",
            "passed": realized_pnl_today > daily_stop,
            "detail": f"pnl={realized_pnl_today} threshold={daily_stop}",
        }
    )
    checks.append(
        {
            "name": "max_trades_not_reached",
            "passed": trades_today < max_trades,
            "detail": f"trades={trades_today}/{max_trades}",
        }
    )

    max_open_positions = int(profile["max_open_positions"])
    open_positions = db.execute(
        select(func.count())
        .select_from(Position)
        .where(
            Position.user_id == current_user.id,
            Position.status == "OPEN",
        )
    ).scalar_one()
    checks.append(
        {
            "name": "max_open_positions_not_reached",
            "passed": int(open_positions) < max_open_positions,
            "detail": f"open={open_positions}/{max_open_positions}",
        }
    )

    cooldown_minutes = float(profile["cooldown_between_trades_minutes"])
    last_trade_at = db.execute(
        select(func.max(func.coalesce(Position.closed_at, Position.opened_at))).where(
            Position.user_id == current_user.id
        )
    ).scalar_one_or_none()
    cooldown_passed = True
    cooldown_detail = "no previous trade"
    if last_trade_at:
        if last_trade_at.tzinfo is None:
            last_trade_at = last_trade_at.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - last_trade_at.astimezone(timezone.utc)).total_seconds() / 60.0
        cooldown_passed = elapsed >= cooldown_minutes
        cooldown_detail = f"elapsed={round(elapsed,2)}m required={cooldown_minutes}m"
    checks.append(
        {
            "name": "cooldown_passed",
            "passed": cooldown_passed,
            "detail": cooldown_detail,
        }
    )

    passed = all(bool(c["passed"]) for c in checks)
    action = "pretrade.check.passed" if passed else "pretrade.check.blocked"
    log_audit_event(
        db,
        action=action,
        user_id=current_user.id,
        entity_type="pretrade",
        details={
            "exchange": exchange,
            "strategy_id": strategy["strategy_id"],
            "strategy_source": strategy["source"],
            "checks": checks,
        },
    )
    db.commit()

    return {
        "passed": passed,
        "exchange": exchange,
        "strategy_id": strategy["strategy_id"],
        "strategy_source": strategy["source"],
        "risk_profile": profile["profile_name"],
        "checks": checks,
    }

@router.get("/health")
def ops_health():
    return {"system_state": "OK", "note": "placeholder"}


@router.get("/audit/me", response_model=list[AuditOut])
def my_audit(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == current_user.id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return rows


@router.get("/audit/all", response_model=list[AuditOut])
def all_audit(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    rows = (
        db.execute(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return rows


@router.get("/risk/daily-compare")
def daily_risk_compare(
    real_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    today = today_colombia()
    users = db.execute(select(User).order_by(User.email.asc())).scalars().all()
    rows = []

    for user in users:
        email_l = (user.email or "").lower()
        if real_only and (
            email_l.startswith("smoke.")
            or email_l.startswith("disabled_")
            or email_l.endswith("@example.com")
            or email_l.endswith("@example.invalid")
        ):
            continue

        profile = resolve_risk_profile_for_email(user.email)
        dr = (
            db.execute(
                select(DailyRiskState).where(
                    DailyRiskState.user_id == user.id,
                    DailyRiskState.day == today,
                )
            )
            .scalar_one_or_none()
        )

        open_positions = db.execute(
            select(func.count())
            .select_from(Position)
            .where(Position.user_id == user.id, Position.status == "OPEN")
        ).scalar_one()
        closed_today = db.execute(
            select(func.count())
            .select_from(Position)
            .where(
                Position.user_id == user.id,
                Position.status == "CLOSED",
                func.date(Position.closed_at) == str(today),
            )
        ).scalar_one()
        blocked_today = db.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.user_id == user.id,
                AuditLog.action.like("position.open.blocked.%"),
                func.date(AuditLog.created_at) == str(today),
            )
        ).scalar_one()

        max_trades = int(dr.max_trades) if dr else int(profile["max_trades_per_day"])
        daily_stop = float(dr.daily_stop) if dr else -abs(float(profile["max_daily_loss_pct"]))
        trades_today = int(dr.trades_today) if dr else 0
        realized_pnl_today = float(dr.realized_pnl_today) if dr else 0.0

        rows.append(
            {
                "user_id": user.id,
                "email": user.email,
                "role": user.role,
                "risk_profile": profile["profile_name"],
                "limits": {
                    "max_risk_per_trade_pct": float(profile["max_risk_per_trade_pct"]),
                    "max_daily_loss_pct": float(profile["max_daily_loss_pct"]),
                    "max_trades_per_day": int(profile["max_trades_per_day"]),
                    "max_open_positions": int(profile["max_open_positions"]),
                    "cooldown_between_trades_minutes": float(profile["cooldown_between_trades_minutes"]),
                    "min_rr": float(profile["min_rr"]),
                },
                "today": {
                    "day": str(today),
                    "trades_today": trades_today,
                    "realized_pnl_today": realized_pnl_today,
                    "daily_stop_threshold": daily_stop,
                    "open_positions_now": int(open_positions),
                    "closed_positions_today": int(closed_today),
                    "blocked_open_attempts_today": int(blocked_today),
                    "trades_utilization_pct": round((trades_today / max_trades) * 100.0, 2) if max_trades > 0 else 0.0,
                },
            }
        )

    return {
        "day": str(today),
        "generated_for": current_user.email,
        "users": rows,
    }


@router.post("/strategy/assign", response_model=StrategyAssignOut)
def assign_strategy(
    payload: StrategyAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    user = db.execute(
        select(User).where(User.email == payload.user_email)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    row = upsert_strategy_assignment(
        db=db,
        user_id=user.id,
        exchange=payload.exchange,
        strategy_id=payload.strategy_id,
        enabled=payload.enabled,
    )
    db.flush()
    log_audit_event(
        db,
        action="strategy.assignment.updated",
        user_id=current_user.id,
        entity_type="strategy_assignment",
        entity_id=row.id,
        details={
            "target_user_id": user.id,
            "target_user_email": user.email,
            "exchange": row.exchange,
            "strategy_id": row.strategy_id,
            "enabled": row.enabled,
        },
    )
    db.commit()
    return {
        "user_id": user.id,
        "user_email": user.email,
        "exchange": row.exchange,
        "strategy_id": row.strategy_id,
        "enabled": bool(row.enabled),
    }


@router.get("/strategy/assignments", response_model=list[StrategyAssignmentOut])
def list_strategy_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    rows = db.execute(
        select(StrategyAssignment, User)
        .join(User, StrategyAssignment.user_id == User.id)
        .order_by(User.email.asc(), StrategyAssignment.exchange.asc())
    ).all()
    return [
        {
            "user_id": strategy.user_id,
            "user_email": user.email,
            "exchange": strategy.exchange,
            "strategy_id": strategy.strategy_id,
            "enabled": bool(strategy.enabled),
        }
        for strategy, user in rows
    ]


@router.post("/execution/pretrade/binance/check", response_model=PretradeCheckOut)
def pretrade_binance_check(
    payload: PretradeCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = payload  # payload reserved for strategy-specific checks in next iteration
    return _evaluate_pretrade_for_user(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
    )


@router.post("/execution/pretrade/ibkr/check", response_model=PretradeCheckOut)
def pretrade_ibkr_check(
    payload: PretradeCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = payload  # payload reserved for strategy-specific checks in next iteration
    return _evaluate_pretrade_for_user(
        db=db,
        current_user=current_user,
        exchange="IBKR",
    )


@router.post("/execution/prepare", response_model=ExecutionPrepareOut)
def prepare_execution(
    payload: ExecutionPrepareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange=payload.exchange,
    )
    result = prepare_execution_for_user(
        user_id=current_user.id,
        exchange=payload.exchange,
        symbol=payload.symbol,
        side=payload.side,
        qty=payload.qty,
    )
    return result


@router.post("/execution/binance/test-order", response_model=BinanceTestOrderOut)
def execution_binance_test_order(
    payload: BinanceTestOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
    )
    result = execute_binance_test_order_for_user(
        user_id=current_user.id,
        symbol=payload.symbol,
        side=payload.side,
        qty=payload.qty,
    )
    return result


@router.post("/execution/ibkr/test-order", response_model=IbkrTestOrderOut)
def execution_ibkr_test_order(
    payload: IbkrTestOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="IBKR",
    )
    result = execute_ibkr_test_order_for_user(
        user_id=current_user.id,
        symbol=payload.symbol,
        side=payload.side,
        qty=payload.qty,
    )
    return result


@router.post("/security/reencrypt-exchange-secrets", response_model=ReencryptSecretsOut)
def security_reencrypt_exchange_secrets(
    payload: ReencryptSecretsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = reencrypt_exchange_secrets(
        db=db,
        old_key=payload.old_key,
        new_key=payload.new_key,
        dry_run=payload.dry_run,
    )
    log_audit_event(
        db,
        action="security.key_rotation.reencrypt",
        user_id=current_user.id,
        entity_type="security",
        details={"dry_run": payload.dry_run, "updated": result["updated"]},
    )
    db.commit()
    return result
