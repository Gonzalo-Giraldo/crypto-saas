from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from apps.api.app.api.deps import get_current_user, require_role
from apps.api.app.db.session import get_db
from apps.api.app.models.audit_log import AuditLog
from apps.api.app.models.daily_risk import DailyRiskState
from apps.api.app.models.exchange_secret import ExchangeSecret
from apps.api.app.models.position import Position
from apps.api.app.models.signal import Signal
from apps.api.app.models.strategy_assignment import StrategyAssignment
from apps.api.app.models.user_2fa import UserTwoFactor
from apps.api.app.schemas.execution import (
    BinanceTestOrderOut,
    BinanceTestOrderRequest,
    IbkrTestOrderOut,
    IbkrTestOrderRequest,
    ExecutionPrepareOut,
    ExecutionPrepareRequest,
)
from apps.api.app.schemas.strategy import (
    ExitCheckOut,
    ExitCheckRequest,
    PretradeCheckOut,
    PretradeCheckRequest,
    StrategyAssignmentOut,
    StrategyAssignOut,
    StrategyAssignRequest,
)
from apps.api.app.schemas.security import (
    ReencryptSecretsOut,
    ReencryptSecretsRequest,
    CleanupSmokeUsersOut,
    CleanupSmokeUsersUserOut,
    DashboardSummaryOut,
    DashboardSecurityOut,
    DashboardOperationsOut,
    DashboardEventsOut,
    DashboardProfileProductivityOut,
    DashboardTrendDayOut,
    DashboardUserOut,
    SecurityPostureOut,
    SecurityPostureSummaryOut,
    SecurityPostureUserOut,
    TradingControlOut,
    TradingControlUpdateRequest,
)
from apps.api.app.models.user import User
from apps.api.app.schemas.audit import AuditOut
from apps.api.app.core.time import today_colombia
from apps.api.app.services.audit import log_audit_event
from apps.api.app.services.key_rotation import reencrypt_exchange_secrets
from apps.api.app.services.risk_profiles import resolve_risk_profile
from apps.api.app.services.idempotency import (
    consume_idempotent_response,
    store_idempotent_response,
)
from apps.api.app.services.trading_controls import (
    assert_exposure_limits,
    assert_trading_enabled,
    get_trading_enabled,
    set_trading_enabled,
)
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


def _is_real_user_email(email: str) -> bool:
    e = (email or "").lower()
    if e.startswith("smoke.") or e.startswith("disabled_"):
        return False
    if e.endswith("@example.com") or e.endswith("@example.invalid"):
        return False
    return True


def _build_security_posture_rows(
    db: Session,
    *,
    real_only: bool,
    max_secret_age_days: int,
):
    now = datetime.now(timezone.utc)
    users = db.execute(select(User).order_by(User.email.asc())).scalars().all()
    posture_rows: list[SecurityPostureUserOut] = []
    missing_2fa = 0
    stale_secrets = 0

    for user in users:
        if real_only and not _is_real_user_email(user.email):
            continue

        user_2fa = (
            db.execute(
                select(UserTwoFactor).where(UserTwoFactor.user_id == user.id)
            )
            .scalar_one_or_none()
        )
        two_factor_enabled = bool(user_2fa and user_2fa.enabled)

        secret_rows = db.execute(
            select(ExchangeSecret.exchange, ExchangeSecret.updated_at).where(
                ExchangeSecret.user_id == user.id
            )
        ).all()
        configured_exchanges = {row[0] for row in secret_rows}

        oldest_days: Optional[int] = None
        for _, updated_at in secret_rows:
            if updated_at is None:
                continue
            ts = updated_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_days = max(0, int((now - ts.astimezone(timezone.utc)).total_seconds() // 86400))
            if oldest_days is None or age_days > oldest_days:
                oldest_days = age_days

        stale = oldest_days is not None and oldest_days > max_secret_age_days
        if stale:
            stale_secrets += 1

        if user.role in {"admin", "trader"} and not two_factor_enabled:
            missing_2fa += 1

        posture_rows.append(
            SecurityPostureUserOut(
                user_id=user.id,
                email=user.email,
                role=user.role,
                two_factor_enabled=two_factor_enabled,
                binance_secret_configured="BINANCE" in configured_exchanges,
                ibkr_secret_configured="IBKR" in configured_exchanges,
                oldest_secret_age_days=oldest_days,
                stale_secret=stale,
            )
        )

    return now, posture_rows, missing_2fa, stale_secrets


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
    payload: PretradeCheckRequest,
):
    strategy = resolve_strategy_for_user_exchange(
        db=db,
        user_id=current_user.id,
        exchange=exchange,
    )
    profile = resolve_risk_profile(db, current_user.id, current_user.email)
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

    strategy_id = strategy["strategy_id"]
    strategy_checks = _build_strategy_checks(
        exchange=exchange,
        strategy_id=strategy_id,
        payload=payload,
    )
    checks.extend(strategy_checks)

    passed = all(bool(c["passed"]) for c in checks)
    action = "pretrade.check.passed" if passed else "pretrade.check.blocked"
    log_audit_event(
        db,
        action=action,
        user_id=current_user.id,
        entity_type="pretrade",
        details={
            "exchange": exchange,
            "strategy_id": strategy_id,
            "strategy_source": strategy["source"],
            "request": {
                "symbol": payload.symbol,
                "side": payload.side,
                "qty": payload.qty,
                "rr_estimate": payload.rr_estimate,
                "trend_tf": payload.trend_tf,
                "signal_tf": payload.signal_tf,
                "timing_tf": payload.timing_tf,
            },
            "checks": checks,
        },
    )
    db.commit()

    return {
        "passed": passed,
        "exchange": exchange,
        "strategy_id": strategy_id,
        "strategy_source": strategy["source"],
        "risk_profile": profile["profile_name"],
        "checks": checks,
    }


def _build_strategy_checks(
    exchange: str,
    strategy_id: str,
    payload: PretradeCheckRequest,
) -> list[dict]:
    checks: list[dict] = []
    ex = exchange.upper()
    st = strategy_id.upper()

    if st == "INTRADAY_V1":
        rr_min = 1.3
        allowed_trend_tfs = {"1H"}
        allowed_signal_tfs = {"15M"}
        allowed_timing_tfs = {"5M", "15M"}
    else:
        rr_min = 1.5
        if ex == "IBKR":
            allowed_trend_tfs = {"1D", "4H"}
            allowed_signal_tfs = {"1H", "30M"}
            allowed_timing_tfs = {"5M", "15M"}
        else:
            allowed_trend_tfs = {"4H"}
            allowed_signal_tfs = {"1H"}
            allowed_timing_tfs = {"15M"}

    checks.append(
        {
            "name": "strategy_rr_min",
            "passed": float(payload.rr_estimate) >= rr_min,
            "detail": f"rr={payload.rr_estimate} required>={rr_min}",
        }
    )
    checks.append(
        {
            "name": "strategy_trend_tf",
            "passed": payload.trend_tf in allowed_trend_tfs,
            "detail": f"value={payload.trend_tf} allowed={sorted(allowed_trend_tfs)}",
        }
    )
    checks.append(
        {
            "name": "strategy_signal_tf",
            "passed": payload.signal_tf in allowed_signal_tfs,
            "detail": f"value={payload.signal_tf} allowed={sorted(allowed_signal_tfs)}",
        }
    )
    checks.append(
        {
            "name": "strategy_timing_tf",
            "passed": payload.timing_tf in allowed_timing_tfs,
            "detail": f"value={payload.timing_tf} allowed={sorted(allowed_timing_tfs)}",
        }
    )

    if ex == "BINANCE":
        if st == "INTRADAY_V1":
            min_volume = 80_000_000.0
            max_spread = 8.0
            max_slippage = 12.0
        else:
            min_volume = 50_000_000.0
            max_spread = 10.0
            max_slippage = 15.0

        checks.append(
            {
                "name": "liq_volume_24h",
                "passed": float(payload.volume_24h_usdt) >= min_volume,
                "detail": f"value={payload.volume_24h_usdt} required>={min_volume}",
            }
        )
        checks.append(
            {
                "name": "liq_spread_bps",
                "passed": float(payload.spread_bps) <= max_spread,
                "detail": f"value={payload.spread_bps} required<={max_spread}",
            }
        )
        checks.append(
            {
                "name": "liq_slippage_bps",
                "passed": float(payload.slippage_bps) <= max_slippage,
                "detail": f"value={payload.slippage_bps} required<={max_slippage}",
            }
        )
    else:
        checks.append(
            {
                "name": "ibkr_in_rth",
                "passed": bool(payload.in_rth),
                "detail": "must be true",
            }
        )
        checks.append(
            {
                "name": "ibkr_no_macro_block",
                "passed": not bool(payload.macro_event_block),
                "detail": f"macro_event_block={payload.macro_event_block}",
            }
        )
        checks.append(
            {
                "name": "ibkr_no_earnings_24h",
                "passed": not bool(payload.earnings_within_24h),
                "detail": f"earnings_within_24h={payload.earnings_within_24h}",
            }
        )

    return checks


def _build_exit_checks(
    exchange: str,
    strategy_id: str,
    payload: ExitCheckRequest,
) -> tuple[list[dict], list[str]]:
    ex = exchange.upper()
    st = strategy_id.upper()
    checks: list[dict] = []
    reasons: list[str] = []

    side = payload.side.upper()
    entry = float(payload.entry_price)
    current = float(payload.current_price)
    stop = float(payload.stop_loss)
    take = float(payload.take_profit)
    opened_minutes = int(payload.opened_minutes)

    if side == "BUY":
        sl_hit = current <= stop
        tp_hit = current >= take
    else:
        sl_hit = current >= stop
        tp_hit = current <= take

    checks.append({"name": "exit_stop_loss_hit", "passed": sl_hit, "detail": f"current={current} stop={stop}"})
    checks.append({"name": "exit_take_profit_hit", "passed": tp_hit, "detail": f"current={current} take_profit={take}"})
    if sl_hit:
        reasons.append("stop_loss_hit")
    if tp_hit:
        reasons.append("take_profit_hit")

    if st == "INTRADAY_V1":
        max_hold_minutes = 240
    else:
        max_hold_minutes = 480

    timeout = opened_minutes >= max_hold_minutes
    checks.append(
        {
            "name": "exit_time_limit",
            "passed": timeout,
            "detail": f"opened_minutes={opened_minutes} limit={max_hold_minutes}",
        }
    )
    if timeout:
        reasons.append("time_limit_reached")

    trend_break = bool(payload.trend_break)
    signal_reverse = bool(payload.signal_reverse)
    checks.append({"name": "exit_trend_break", "passed": trend_break, "detail": f"trend_break={trend_break}"})
    checks.append({"name": "exit_signal_reverse", "passed": signal_reverse, "detail": f"signal_reverse={signal_reverse}"})
    if trend_break:
        reasons.append("trend_break")
    if signal_reverse:
        reasons.append("signal_reverse")

    if ex == "IBKR":
        event_forced_exit = bool(payload.macro_event_block) or bool(payload.earnings_within_24h)
        checks.append(
            {
                "name": "exit_event_risk",
                "passed": event_forced_exit,
                "detail": f"macro_event_block={payload.macro_event_block} earnings_within_24h={payload.earnings_within_24h}",
            }
        )
        if event_forced_exit:
            reasons.append("event_risk_exit")

    # Deduplicate while preserving order.
    uniq_reasons = list(dict.fromkeys(reasons))
    return checks, uniq_reasons

@router.get("/health")
def ops_health():
    return {"system_state": "OK", "note": "placeholder"}


@router.get("/admin/trading-control", response_model=TradingControlOut)
def get_admin_trading_control(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    enabled = get_trading_enabled(db)
    return TradingControlOut(
        trading_enabled=enabled,
        updated_by=current_user.email,
        reason=None,
    )


@router.post("/admin/trading-control", response_model=TradingControlOut)
def update_admin_trading_control(
    payload: TradingControlUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    set_trading_enabled(db, enabled=payload.trading_enabled)
    log_audit_event(
        db,
        action="security.trading_control.updated",
        user_id=current_user.id,
        entity_type="security",
        details={
            "trading_enabled": payload.trading_enabled,
            "reason": payload.reason,
        },
    )
    db.commit()
    return TradingControlOut(
        trading_enabled=payload.trading_enabled,
        updated_by=current_user.email,
        reason=payload.reason,
    )


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

        profile = resolve_risk_profile(db, user.id, user.email)
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
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_trading_enabled(
        db=db,
        current_user=current_user,
        action="pretrade_check",
        exchange="BINANCE",
    )
    assert_exposure_limits(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
        symbol=payload.symbol,
        qty=payload.qty,
        price_estimate=0.0,
    )
    req_payload = payload.model_dump()
    cached = consume_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/pretrade/binance/check",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
    )
    if cached is not None:
        return cached

    result = _evaluate_pretrade_for_user(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
        payload=payload,
    )
    store_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/pretrade/binance/check",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
        response_payload=result,
    )
    return result


@router.post("/execution/pretrade/ibkr/check", response_model=PretradeCheckOut)
def pretrade_ibkr_check(
    payload: PretradeCheckRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_trading_enabled(
        db=db,
        current_user=current_user,
        action="pretrade_check",
        exchange="IBKR",
    )
    assert_exposure_limits(
        db=db,
        current_user=current_user,
        exchange="IBKR",
        symbol=payload.symbol,
        qty=payload.qty,
        price_estimate=0.0,
    )
    req_payload = payload.model_dump()
    cached = consume_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/pretrade/ibkr/check",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
    )
    if cached is not None:
        return cached

    result = _evaluate_pretrade_for_user(
        db=db,
        current_user=current_user,
        exchange="IBKR",
        payload=payload,
    )
    store_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/pretrade/ibkr/check",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
        response_payload=result,
    )
    return result


@router.post("/execution/exit/binance/check", response_model=ExitCheckOut)
def exit_binance_check(
    payload: ExitCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
    )
    strategy = resolve_strategy_for_user_exchange(
        db=db,
        user_id=current_user.id,
        exchange="BINANCE",
    )
    checks, reasons = _build_exit_checks(
        exchange="BINANCE",
        strategy_id=strategy["strategy_id"],
        payload=payload,
    )
    should_exit = len(reasons) > 0
    log_audit_event(
        db,
        action="exit.check.triggered" if should_exit else "exit.check.hold",
        user_id=current_user.id,
        entity_type="exit",
        details={
            "exchange": "BINANCE",
            "strategy_id": strategy["strategy_id"],
            "strategy_source": strategy["source"],
            "should_exit": should_exit,
            "reasons": reasons,
            "checks": checks,
        },
    )
    db.commit()
    return {
        "should_exit": should_exit,
        "exchange": "BINANCE",
        "strategy_id": strategy["strategy_id"],
        "strategy_source": strategy["source"],
        "reasons": reasons,
        "checks": checks,
    }


@router.post("/execution/exit/ibkr/check", response_model=ExitCheckOut)
def exit_ibkr_check(
    payload: ExitCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="IBKR",
    )
    strategy = resolve_strategy_for_user_exchange(
        db=db,
        user_id=current_user.id,
        exchange="IBKR",
    )
    checks, reasons = _build_exit_checks(
        exchange="IBKR",
        strategy_id=strategy["strategy_id"],
        payload=payload,
    )
    should_exit = len(reasons) > 0
    log_audit_event(
        db,
        action="exit.check.triggered" if should_exit else "exit.check.hold",
        user_id=current_user.id,
        entity_type="exit",
        details={
            "exchange": "IBKR",
            "strategy_id": strategy["strategy_id"],
            "strategy_source": strategy["source"],
            "should_exit": should_exit,
            "reasons": reasons,
            "checks": checks,
        },
    )
    db.commit()
    return {
        "should_exit": should_exit,
        "exchange": "IBKR",
        "strategy_id": strategy["strategy_id"],
        "strategy_source": strategy["source"],
        "reasons": reasons,
        "checks": checks,
    }


@router.post("/execution/prepare", response_model=ExecutionPrepareOut)
def prepare_execution(
    payload: ExecutionPrepareRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_trading_enabled(
        db=db,
        current_user=current_user,
        action="execution_prepare",
        exchange=payload.exchange,
    )
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange=payload.exchange,
    )
    assert_exposure_limits(
        db=db,
        current_user=current_user,
        exchange=payload.exchange,
        symbol=payload.symbol,
        qty=payload.qty,
        price_estimate=0.0,
    )
    req_payload = payload.model_dump()
    cached = consume_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/prepare",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
    )
    if cached is not None:
        return cached

    result = prepare_execution_for_user(
        user_id=current_user.id,
        exchange=payload.exchange,
        symbol=payload.symbol,
        side=payload.side,
        qty=payload.qty,
    )
    store_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/prepare",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
        response_payload=result,
    )
    return result


@router.post("/execution/binance/test-order", response_model=BinanceTestOrderOut)
def execution_binance_test_order(
    payload: BinanceTestOrderRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_trading_enabled(
        db=db,
        current_user=current_user,
        action="test_order",
        exchange="BINANCE",
    )
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
    )
    assert_exposure_limits(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
        symbol=payload.symbol,
        qty=payload.qty,
        price_estimate=0.0,
    )
    req_payload = payload.model_dump()
    cached = consume_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/binance/test-order",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
    )
    if cached is not None:
        return cached

    result = execute_binance_test_order_for_user(
        user_id=current_user.id,
        symbol=payload.symbol,
        side=payload.side,
        qty=payload.qty,
    )
    store_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/binance/test-order",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
        response_payload=result,
    )
    return result


@router.post("/execution/ibkr/test-order", response_model=IbkrTestOrderOut)
def execution_ibkr_test_order(
    payload: IbkrTestOrderRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assert_trading_enabled(
        db=db,
        current_user=current_user,
        action="test_order",
        exchange="IBKR",
    )
    _assert_exchange_enabled(
        db=db,
        current_user=current_user,
        exchange="IBKR",
    )
    assert_exposure_limits(
        db=db,
        current_user=current_user,
        exchange="IBKR",
        symbol=payload.symbol,
        qty=payload.qty,
        price_estimate=0.0,
    )
    req_payload = payload.model_dump()
    cached = consume_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/ibkr/test-order",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
    )
    if cached is not None:
        return cached

    result = execute_ibkr_test_order_for_user(
        user_id=current_user.id,
        symbol=payload.symbol,
        side=payload.side,
        qty=payload.qty,
    )
    store_idempotent_response(
        db,
        user_id=current_user.id,
        endpoint="/ops/execution/ibkr/test-order",
        idempotency_key=idempotency_key,
        request_payload=req_payload,
        response_payload=result,
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


@router.get("/security/posture", response_model=SecurityPostureOut)
def security_posture(
    real_only: bool = False,
    max_secret_age_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    now, posture_rows, missing_2fa, stale_secrets = _build_security_posture_rows(
        db,
        real_only=real_only,
        max_secret_age_days=max_secret_age_days,
    )

    log_audit_event(
        db,
        action="security.posture.read",
        user_id=current_user.id,
        entity_type="security",
        details={
            "real_only": real_only,
            "max_secret_age_days": max_secret_age_days,
            "users": len(posture_rows),
            "missing_2fa": missing_2fa,
            "stale_secrets": stale_secrets,
        },
    )
    db.commit()

    return SecurityPostureOut(
        generated_at=now.isoformat(),
        max_secret_age_days=max_secret_age_days,
        real_only=real_only,
        summary=SecurityPostureSummaryOut(
            total_users=len(posture_rows),
            users_missing_2fa=missing_2fa,
            users_with_stale_secrets=stale_secrets,
        ),
        users=posture_rows,
    )


def _max_dt(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    out = max(vals)
    if out.tzinfo is None:
        out = out.replace(tzinfo=timezone.utc)
    return out


@router.post("/admin/cleanup-smoke-users", response_model=CleanupSmokeUsersOut)
def cleanup_smoke_users(
    dry_run: bool = True,
    older_than_days: int = 14,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(0, older_than_days))
    smoke_users = db.execute(
        select(User).where(User.email.like("smoke.%")).order_by(User.email.asc())
    ).scalars().all()

    rows: list[CleanupSmokeUsersUserOut] = []
    eligible_ids: list[str] = []

    for u in smoke_users:
        last_audit = db.execute(
            select(func.max(AuditLog.created_at)).where(AuditLog.user_id == u.id)
        ).scalar_one()
        last_position_open = db.execute(
            select(func.max(Position.opened_at)).where(Position.user_id == u.id)
        ).scalar_one()
        last_position_close = db.execute(
            select(func.max(Position.closed_at)).where(Position.user_id == u.id)
        ).scalar_one()
        last_signal = db.execute(
            select(func.max(Signal.updated_at)).where(Signal.user_id == u.id)
        ).scalar_one()
        last_secret = db.execute(
            select(func.max(ExchangeSecret.updated_at)).where(ExchangeSecret.user_id == u.id)
        ).scalar_one()
        last_assignment = db.execute(
            select(func.max(StrategyAssignment.updated_at)).where(StrategyAssignment.user_id == u.id)
        ).scalar_one()

        last_activity = _max_dt(
            [
                last_audit,
                last_position_open,
                last_position_close,
                last_signal,
                last_secret,
                last_assignment,
            ]
        )
        eligible = last_activity is None or last_activity < cutoff
        if eligible:
            eligible_ids.append(u.id)

        rows.append(
            CleanupSmokeUsersUserOut(
                user_id=u.id,
                email=u.email,
                last_activity_at=last_activity.isoformat() if last_activity else None,
                eligible_for_delete=eligible,
            )
        )

    deleted = 0
    if not dry_run and eligible_ids:
        db.query(AuditLog).filter(AuditLog.user_id.in_(eligible_ids)).delete(synchronize_session=False)
        db.query(DailyRiskState).filter(DailyRiskState.user_id.in_(eligible_ids)).delete(synchronize_session=False)
        db.query(Position).filter(Position.user_id.in_(eligible_ids)).delete(synchronize_session=False)
        db.query(Signal).filter(Signal.user_id.in_(eligible_ids)).delete(synchronize_session=False)
        db.query(ExchangeSecret).filter(ExchangeSecret.user_id.in_(eligible_ids)).delete(synchronize_session=False)
        db.query(StrategyAssignment).filter(StrategyAssignment.user_id.in_(eligible_ids)).delete(synchronize_session=False)
        db.query(UserTwoFactor).filter(UserTwoFactor.user_id.in_(eligible_ids)).delete(synchronize_session=False)
        deleted = db.query(User).filter(User.id.in_(eligible_ids)).delete(synchronize_session=False)

    log_audit_event(
        db,
        action="ops.cleanup.smoke_users",
        user_id=current_user.id,
        entity_type="ops",
        details={
            "dry_run": dry_run,
            "older_than_days": older_than_days,
            "scanned": len(smoke_users),
            "eligible": len(eligible_ids),
            "deleted": deleted,
        },
    )
    db.commit()

    return CleanupSmokeUsersOut(
        dry_run=dry_run,
        older_than_days=older_than_days,
        scanned=len(smoke_users),
        eligible=len(eligible_ids),
        deleted=deleted,
        users=rows,
    )


@router.get("/dashboard/summary", response_model=DashboardSummaryOut)
def dashboard_summary(
    real_only: bool = True,
    max_secret_age_days: int = 30,
    recent_hours: int = 24,
    email_contains: Optional[str] = None,
    exchange: str = "ALL",
    include_service_users: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    now, posture_rows, missing_2fa, stale_secrets = _build_security_posture_rows(
        db,
        real_only=real_only,
        max_secret_age_days=max_secret_age_days,
    )
    today = today_colombia()

    posture_map = {row.user_id: row for row in posture_rows}
    user_status_rows: list[DashboardUserOut] = []
    profile_agg: dict[str, dict[str, float]] = {}
    trades_today_total = 0
    open_positions_total = 0
    blocked_open_attempts_total = 0

    users = db.execute(select(User).order_by(User.email.asc())).scalars().all()
    for user in users:
        if user.id not in posture_map:
            continue
        email_l = (user.email or "").lower()
        if not include_service_users and email_l.startswith("ops.bot."):
            continue
        if email_contains and email_contains.lower() not in (user.email or "").lower():
            continue

        profile = resolve_risk_profile(db, user.id, user.email)
        p = posture_map[user.id]
        exchange_u = (exchange or "ALL").upper()
        if exchange_u == "BINANCE" and not p.binance_secret_configured:
            continue
        if exchange_u == "IBKR" and not p.ibkr_secret_configured:
            continue

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
        blocked_today = db.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.user_id == user.id,
                AuditLog.action.like("position.open.blocked.%"),
                func.date(AuditLog.created_at) == str(today),
            )
        ).scalar_one()

        trades_today = int(dr.trades_today) if dr else 0
        realized_pnl_today = float(dr.realized_pnl_today) if dr else 0.0

        trades_today_total += trades_today
        open_positions_total += int(open_positions)
        blocked_open_attempts_total += int(blocked_today)

        profile_name = str(profile["profile_name"])
        max_trades_profile = int(profile["max_trades_per_day"])
        bucket = profile_agg.setdefault(
            profile_name,
            {
                "users_count": 0,
                "trades_today_total": 0,
                "blocked_open_attempts_total": 0,
                "realized_pnl_today_total": 0.0,
                "max_trades_capacity_total": 0,
            },
        )
        bucket["users_count"] += 1
        bucket["trades_today_total"] += trades_today
        bucket["blocked_open_attempts_total"] += int(blocked_today)
        bucket["realized_pnl_today_total"] += realized_pnl_today
        bucket["max_trades_capacity_total"] += max_trades_profile

        user_status_rows.append(
            DashboardUserOut(
                user_id=user.id,
                email=user.email,
                role=user.role,
                risk_profile=profile["profile_name"],
                two_factor_enabled=bool(p.two_factor_enabled),
                binance_secret_configured=bool(p.binance_secret_configured),
                ibkr_secret_configured=bool(p.ibkr_secret_configured),
                trades_today=trades_today,
                open_positions_now=int(open_positions),
                blocked_open_attempts_today=int(blocked_today),
                realized_pnl_today=realized_pnl_today,
            )
        )

    scope_user_ids = [u.user_id for u in user_status_rows]
    profile_productivity: list[DashboardProfileProductivityOut] = []
    for profile_name in sorted(profile_agg.keys()):
        p = profile_agg[profile_name]
        users_count = int(p["users_count"])
        trades_total = int(p["trades_today_total"])
        blocked_total = int(p["blocked_open_attempts_total"])
        pnl_total = float(p["realized_pnl_today_total"])
        capacity = int(p["max_trades_capacity_total"])
        avg_pnl = round((pnl_total / users_count), 4) if users_count > 0 else 0.0
        util = round((trades_total / capacity) * 100.0, 2) if capacity > 0 else 0.0
        profile_productivity.append(
            DashboardProfileProductivityOut(
                risk_profile=profile_name,
                users_count=users_count,
                trades_today_total=trades_total,
                blocked_open_attempts_total=blocked_total,
                realized_pnl_today_total=round(pnl_total, 4),
                avg_realized_pnl_per_user=avg_pnl,
                trades_utilization_pct=util,
            )
        )

    cutoff = now - timedelta(hours=recent_hours)
    errors_last_24h = db.execute(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.created_at >= cutoff,
            or_(
                AuditLog.action.like("%.error"),
                AuditLog.action.like("execution.blocked.%"),
            ),
        )
    ).scalar_one()

    pretrade_blocked_last_24h = db.execute(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "pretrade.check.blocked",
            AuditLog.created_at >= cutoff,
        )
    ).scalar_one()

    trends_7d: list[DashboardTrendDayOut] = []
    for i in range(6, -1, -1):
        day_i = today - timedelta(days=i)

        if scope_user_ids:
            trades_agg = db.execute(
                select(func.coalesce(func.sum(DailyRiskState.trades_today), 0)).where(
                    DailyRiskState.day == day_i,
                    DailyRiskState.user_id.in_(scope_user_ids),
                )
            ).scalar_one()
            blocked_agg = db.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.user_id.in_(scope_user_ids),
                    AuditLog.action.like("position.open.blocked.%"),
                    func.date(AuditLog.created_at) == str(day_i),
                )
            ).scalar_one()
            errors_agg = db.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.user_id.in_(scope_user_ids),
                    func.date(AuditLog.created_at) == str(day_i),
                    or_(
                        AuditLog.action.like("%.error"),
                        AuditLog.action.like("execution.blocked.%"),
                    ),
                )
            ).scalar_one()
        else:
            trades_agg = 0
            blocked_agg = 0
            errors_agg = 0

        trends_7d.append(
            DashboardTrendDayOut(
                day=str(day_i),
                trades_total=int(trades_agg or 0),
                blocked_open_attempts_total=int(blocked_agg or 0),
                errors_total=int(errors_agg or 0),
            )
        )

    overall_status = "green"
    if missing_2fa > 0 or stale_secrets > 0:
        overall_status = "red"
    elif blocked_open_attempts_total > 0:
        overall_status = "yellow"

    return DashboardSummaryOut(
        generated_at=now.isoformat(),
        day=str(today),
        overall_status=overall_status,
        generated_for=current_user.email,
        security=DashboardSecurityOut(
            total_users=len(posture_rows),
            users_missing_2fa=missing_2fa,
            users_with_stale_secrets=stale_secrets,
            max_secret_age_days=max_secret_age_days,
        ),
        operations=DashboardOperationsOut(
            trades_today_total=trades_today_total,
            open_positions_total=open_positions_total,
            blocked_open_attempts_total=blocked_open_attempts_total,
        ),
        recent_events=DashboardEventsOut(
            errors_last_24h=int(errors_last_24h),
            pretrade_blocked_last_24h=int(pretrade_blocked_last_24h),
        ),
        profile_productivity=profile_productivity,
        trends_7d=trends_7d,
        users=user_status_rows,
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page():
    return HTMLResponse(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Ops Dashboard</title>
  <style>
    :root { --bg:#f5f7f9; --card:#ffffff; --text:#142033; --muted:#5b677a; --ok:#117a3e; --warn:#a35b00; --bad:#b42318; --line:#dde3ea; }
    * { box-sizing:border-box; }
    body { margin:0; font-family: "Segoe UI", Tahoma, sans-serif; background:linear-gradient(180deg,#eef4ff 0%,var(--bg) 45%); color:var(--text); }
    .wrap { max-width:1100px; margin:24px auto; padding:0 16px 32px; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px; margin-bottom:14px; }
    h1 { margin:0 0 6px; font-size:28px; }
    .muted { color:var(--muted); font-size:13px; }
    .row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
    input { width:420px; max-width:100%; border:1px solid var(--line); border-radius:10px; padding:10px 12px; }
    button { border:0; border-radius:10px; padding:10px 14px; font-weight:600; cursor:pointer; background:#0b62d6; color:#fff; }
    .ghost { background:#eef3fb; color:#0b62d6; border:1px solid #bcd0f4; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:10px; }
    .kpi { border:1px solid var(--line); border-radius:10px; padding:10px; }
    .kpi .v { font-size:24px; font-weight:700; }
    .trend-grid { display:grid; grid-template-columns:1fr; gap:8px; }
    table { width:100%; border-collapse:collapse; }
    th,td { border-bottom:1px solid var(--line); text-align:left; padding:8px 6px; font-size:13px; }
    .badge { display:inline-block; padding:3px 9px; border-radius:999px; font-weight:700; font-size:12px; color:#fff; }
    .tag { display:inline-block; padding:2px 8px; border-radius:999px; font-weight:700; font-size:11px; margin-right:4px; }
    .tag-binance { background:#fff3d0; color:#7a5200; border:1px solid #e7c060; }
    .tag-ibkr { background:#dcecff; color:#164a8a; border:1px solid #90b6ea; }
    .tag-off { background:#f1f4f8; color:#667085; border:1px solid #d0d7e2; }
    .green { background:var(--ok); }
    .yellow { background:var(--warn); }
    .red { background:var(--bad); }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Ops Dashboard</h1>
      <div class="muted">Single-screen view for health, security posture and daily operations.</div>
      <div class="row" style="margin-top:12px">
        <input id="token" placeholder="Paste admin bearer token here" />
        <button id="load">Load</button>
        <label style="display:flex;align-items:center;gap:6px;font-size:12px;color:#445066;">
          <input id="rememberToken" type="checkbox" />
          Remember token
        </label>
        <input id="emailFilter" placeholder="email contains (optional)" />
        <select id="realOnlyFilter" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;">
          <option value="true">real_only=true</option>
          <option value="false">real_only=false</option>
        </select>
        <select id="exchangeFilter" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;">
          <option value="ALL">ALL</option>
          <option value="BINANCE">BINANCE</option>
          <option value="IBKR">IBKR</option>
        </select>
        <button id="resetBtn" class="ghost">Reset Filters</button>
        <button id="incidentBtn" class="ghost">Open Incident</button>
      </div>
      <div class="row" style="margin-top:10px">
        <input id="loginEmail" placeholder="admin email (for auto token)" />
        <input id="loginPassword" type="password" placeholder="admin password" />
        <input id="loginOtp" placeholder="otp (if required)" style="width:180px" />
        <button id="loginBtn" class="ghost">Get Token</button>
      </div>
      <div class="muted" id="stamp" style="margin-top:8px">Waiting for token...</div>
    </div>
    <div class="card">
      <div class="row"><strong>Overall status:</strong> <span id="overall" class="badge yellow">unknown</span></div>
      <div class="grid" style="margin-top:10px">
        <div class="kpi"><div class="muted">Users in scope</div><div id="k_users" class="v">-</div></div>
        <div class="kpi"><div class="muted">Missing 2FA</div><div id="k_2fa" class="v">-</div></div>
        <div class="kpi"><div class="muted">Stale secrets</div><div id="k_stale" class="v">-</div></div>
        <div class="kpi"><div class="muted">Trades today</div><div id="k_trades" class="v">-</div></div>
        <div class="kpi"><div class="muted">Open positions</div><div id="k_open" class="v">-</div></div>
        <div class="kpi"><div class="muted">Blocked opens today</div><div id="k_blocked" class="v">-</div></div>
      </div>
    </div>
    <div class="card">
      <strong>Profile Productivity</strong>
      <div class="muted" style="margin:4px 0 10px">Daily comparison by risk profile (conservative vs loose).</div>
      <table>
        <thead>
          <tr><th>Risk profile</th><th>Users</th><th>Trades</th><th>Utilization %</th><th>Blocked opens</th><th>PnL total</th><th>Avg PnL/user</th></tr>
        </thead>
        <tbody id="profileBody"><tr><td colspan="7" class="muted">No profile data yet</td></tr></tbody>
      </table>
    </div>
    <div class="card">
      <strong>7-day trend</strong>
      <div class="muted" style="margin:4px 0 10px">Trades, blocked opens and errors per day.</div>
      <table>
        <thead>
          <tr><th>Day</th><th>Trades</th><th>Blocked opens</th><th>Errors</th></tr>
        </thead>
        <tbody id="trendBody"><tr><td colspan="4" class="muted">No trend data yet</td></tr></tbody>
      </table>
    </div>
    <div class="card">
      <strong>Users</strong>
      <table>
        <thead>
          <tr><th>Email</th><th>Role</th><th>Risk profile</th><th>Exchanges</th><th>2FA</th><th>Trades</th><th>Open</th><th>Blocked</th><th>Realized PnL</th></tr>
        </thead>
        <tbody id="tbody"><tr><td colspan="9" class="muted">No data yet</td></tr></tbody>
      </table>
    </div>
    <div class="card">
      <strong>User Admin</strong>
      <div class="muted" style="margin:4px 0 10px">Manage users, roles, passwords, risk profile and exchange secrets without SQL.</div>
      <div class="row" style="margin-bottom:10px">
        <input id="newUserEmail" placeholder="new user email" />
        <input id="newUserPassword" type="password" placeholder="new user password" />
        <button id="createUserBtn" class="ghost">Create user</button>
      </div>
      <div class="row" style="margin-bottom:10px">
        <select id="adminUserSelect" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;min-width:320px;"></select>
        <button id="refreshUsersBtn" class="ghost">Refresh users</button>
      </div>
      <div class="row" style="margin-bottom:10px">
        <select id="adminRoleSelect" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;">
          <option value="trader">trader</option>
          <option value="admin">admin</option>
          <option value="disabled">disabled</option>
        </select>
        <button id="setRoleBtn">Set role</button>
        <input id="newEmailInput" placeholder="new email (optional)" />
        <button id="setEmailBtn" class="ghost">Update email</button>
      </div>
      <div class="row" style="margin-bottom:10px">
        <select id="adminRiskSelect" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;min-width:260px;"></select>
        <button id="setRiskBtn">Set risk profile</button>
        <button id="clearRiskBtn" class="ghost">Clear risk override</button>
      </div>
      <div class="row" style="margin-bottom:10px">
        <input id="newPasswordInput" type="password" placeholder="new password (min 8 chars)" />
        <button id="setPasswordBtn">Set password</button>
      </div>
      <div class="row" style="margin-bottom:10px">
        <select id="adminExchangeSelect" style="border:1px solid var(--line);border-radius:10px;padding:10px 12px;">
          <option value="BINANCE">BINANCE</option>
          <option value="IBKR">IBKR</option>
        </select>
        <input id="adminApiKey" placeholder="API key" />
        <input id="adminApiSecret" type="password" placeholder="API secret" />
        <button id="setSecretBtn">Save secret</button>
        <button id="deleteSecretBtn" class="ghost">Delete secret</button>
      </div>
      <div class="muted" id="adminMsg">Admin panel idle.</div>
      <table style="margin-top:10px">
        <thead>
          <tr><th>User</th><th>Role</th><th>Risk profile</th><th>Source</th></tr>
        </thead>
        <tbody id="adminUsersBody"><tr><td colspan="4" class="muted">Load dashboard first</td></tr></tbody>
      </table>
    </div>
    <div class="card">
      <strong>User Readiness</strong>
      <div class="muted" style="margin:4px 0 10px">Single table with operability status by user.</div>
      <table>
        <thead>
          <tr><th>User</th><th>Role</th><th>2FA</th><th>Assignments</th><th>Secrets</th><th>Status</th><th>Main reason</th></tr>
        </thead>
        <tbody id="readinessBody"><tr><td colspan="7" class="muted">Load dashboard first</td></tr></tbody>
      </table>
    </div>
  </div>
  <script>
    const byId = (id) => document.getElementById(id);
    const TOKEN_SESSION_KEY = "ops_dashboard_token_session";
    const TOKEN_PERSIST_KEY = "ops_dashboard_token_persist";
    const TOKEN_REMEMBER_KEY = "ops_dashboard_token_remember";
    const LOGIN_EMAIL_KEY = "ops_dashboard_login_email";
    const DEFAULT_RISK_PROFILES = ["model2_conservador_productivo", "modelo_suelto_controlado"];
    const adminState = { users: [], riskProfiles: [...DEFAULT_RISK_PROFILES] };

    function saveToken(token) {
      sessionStorage.setItem(TOKEN_SESSION_KEY, token || "");
      const remember = byId("rememberToken").checked;
      localStorage.setItem(TOKEN_REMEMBER_KEY, remember ? "1" : "0");
      if (remember) {
        localStorage.setItem(TOKEN_PERSIST_KEY, token || "");
      } else {
        localStorage.removeItem(TOKEN_PERSIST_KEY);
      }
    }

    function loadStoredToken() {
      const remember = localStorage.getItem(TOKEN_REMEMBER_KEY) === "1";
      byId("rememberToken").checked = remember;
      const token = remember
        ? (localStorage.getItem(TOKEN_PERSIST_KEY) || "")
        : (sessionStorage.getItem(TOKEN_SESSION_KEY) || "");
      if (token) byId("token").value = token;
      const email = localStorage.getItem(LOGIN_EMAIL_KEY) || "";
      if (email) byId("loginEmail").value = email;
    }

    function setOverall(v) {
      const el = byId("overall");
      el.textContent = v || "unknown";
      el.className = "badge " + (v === "green" ? "green" : v === "red" ? "red" : "yellow");
    }

    function setAdminMsg(msg, isError = false) {
      const el = byId("adminMsg");
      el.textContent = msg;
      el.style.color = isError ? "var(--bad)" : "var(--muted)";
    }

    function authHeaders(token) {
      return {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      };
    }

    async function apiJson(path, token, opts = {}) {
      const headers = opts.headers || authHeaders(token);
      const res = await fetch(path, { ...opts, headers });
      const contentType = res.headers.get("content-type") || "";
      const data = contentType.includes("application/json")
        ? await res.json()
        : { detail: await res.text() };
      if (!res.ok) {
        throw new Error(data.detail || `${res.status} request failed`);
      }
      return data;
    }

    function selectedUserId() {
      return (byId("adminUserSelect").value || "").trim();
    }

    function selectedUserObj() {
      const id = selectedUserId();
      return adminState.users.find((u) => u.id === id) || null;
    }

    function renderRiskProfileOptions() {
      byId("adminRiskSelect").innerHTML = adminState.riskProfiles
        .map((p) => `<option value="${p}">${p}</option>`)
        .join("");
    }

    function renderAdminUsers(preferredUserId = "") {
      const users = adminState.users || [];
      const current = preferredUserId || selectedUserId();
      byId("adminUserSelect").innerHTML = users
        .map((u) => `<option value="${u.id}">${u.email} | ${u.role} | ${u.risk_profile}</option>`)
        .join("");
      if (current && users.some((u) => u.id === current)) {
        byId("adminUserSelect").value = current;
      }

      byId("adminUsersBody").innerHTML = users.map((u) => `<tr>
        <td>${u.email}</td><td>${u.role}</td><td>${u.risk_profile || "-"}</td><td>${u.risk_profile_source || "-"}</td>
      </tr>`).join("") || '<tr><td colspan="4" class="muted">No users found</td></tr>';
    }

    async function loadAdminUsers(preferredUserId = "") {
      const token = byId("token").value.trim();
      if (!token) return;
      const users = await apiJson("/users", token, { method: "GET", headers: { Authorization: `Bearer ${token}` } });
      adminState.users = users || [];
      renderAdminUsers(preferredUserId);
      await renderReadinessTable();
    }

    function fmtAssignments(a) {
      const keys = Object.keys(a || {}).sort();
      if (!keys.length) return "none";
      return keys.map((k) => `${k}:${a[k] ? "on" : "off"}`).join(" | ");
    }

    async function renderReadinessTable() {
      const token = byId("token").value.trim();
      if (!token) return;
      const users = adminState.users || [];
      if (!users.length) {
        byId("readinessBody").innerHTML = '<tr><td colspan="7" class="muted">No users</td></tr>';
        return;
      }
      const rows = await Promise.all(users.map(async (u) => {
        try {
          const r = await apiJson(`/users/${u.id}/readiness-check`, token, {
            method: "GET",
            headers: { Authorization: `Bearer ${token}` },
          });
          const failed = (r.checks || []).find((c) => !c.passed);
          return {
            email: r.email,
            role: r.role,
            two_factor_enabled: r.two_factor_enabled,
            assignments: fmtAssignments(r.assignments),
            secrets: (r.secrets_configured || []).join(", ") || "none",
            ready: !!r.ready,
            reason: failed ? `${failed.name}: ${failed.detail}` : "ok",
          };
        } catch (e) {
          return {
            email: u.email,
            role: u.role,
            two_factor_enabled: false,
            assignments: "n/a",
            secrets: "n/a",
            ready: false,
            reason: String(e.message || e),
          };
        }
      }));
      byId("readinessBody").innerHTML = rows.map((r) => `<tr>
        <td>${r.email}</td>
        <td>${r.role}</td>
        <td>${r.two_factor_enabled ? "yes" : "no"}</td>
        <td>${r.assignments}</td>
        <td>${r.secrets}</td>
        <td><span class="badge ${r.ready ? "green" : "red"}">${r.ready ? "READY" : "MISSING"}</span></td>
        <td>${r.reason}</td>
      </tr>`).join("");
    }

    async function runReadinessCheck(userId) {
      const token = byId("token").value.trim();
      if (!token || !userId) return;
      const readiness = await apiJson(`/users/${userId}/readiness-check`, token, {
        method: "GET",
        headers: { Authorization: `Bearer ${token}` },
      });
      const failed = (readiness.checks || []).filter((c) => !c.passed);
      if (!failed.length) {
        setAdminMsg(`Readiness OK for ${readiness.email}`);
        return;
      }
      const first = failed[0];
      setAdminMsg(`Readiness warning for ${readiness.email}: ${first.name} (${first.detail})`, true);
    }

    async function loadRiskProfiles() {
      const token = byId("token").value.trim();
      if (!token) return;
      try {
        const profiles = await apiJson("/users/risk-profiles", token, { method: "GET", headers: { Authorization: `Bearer ${token}` } });
        adminState.riskProfiles = (profiles && profiles.length) ? profiles : [...DEFAULT_RISK_PROFILES];
      } catch (_) {
        adminState.riskProfiles = [...DEFAULT_RISK_PROFILES];
      }
      renderRiskProfileOptions();
    }

    function fill(d) {
      setOverall(d.overall_status);
      byId("stamp").textContent = `Generated: ${d.generated_at} | Day: ${d.day} | For: ${d.generated_for}`;
      byId("k_users").textContent = d.security.total_users;
      byId("k_2fa").textContent = d.security.users_missing_2fa;
      byId("k_stale").textContent = d.security.users_with_stale_secrets;
      byId("k_trades").textContent = d.operations.trades_today_total;
      byId("k_open").textContent = d.operations.open_positions_total;
      byId("k_blocked").textContent = d.operations.blocked_open_attempts_total;
      byId("profileBody").innerHTML = (d.profile_productivity || []).map(p => `<tr>
        <td>${p.risk_profile}</td><td>${p.users_count}</td><td>${p.trades_today_total}</td><td>${p.trades_utilization_pct}</td><td>${p.blocked_open_attempts_total}</td><td>${p.realized_pnl_today_total}</td><td>${p.avg_realized_pnl_per_user}</td>
      </tr>`).join("") || '<tr><td colspan="7" class="muted">No profile data yet</td></tr>';
      byId("trendBody").innerHTML = (d.trends_7d || []).map(t => `<tr>
        <td>${t.day}</td><td>${t.trades_total}</td><td>${t.blocked_open_attempts_total}</td><td>${t.errors_total}</td>
      </tr>`).join("") || '<tr><td colspan="4" class="muted">No trend data yet</td></tr>';
      byId("tbody").innerHTML = d.users.map(u => `<tr>
        <td>${u.email}</td><td>${u.role}</td><td>${u.risk_profile}</td>
        <td>
          <span class="tag ${u.binance_secret_configured ? "tag-binance" : "tag-off"}">BINANCE ${u.binance_secret_configured ? "on" : "off"}</span>
          <span class="tag ${u.ibkr_secret_configured ? "tag-ibkr" : "tag-off"}">IBKR ${u.ibkr_secret_configured ? "on" : "off"}</span>
        </td>
        <td>${u.two_factor_enabled ? "yes" : "no"}</td>
        <td>${u.trades_today}</td><td>${u.open_positions_now}</td><td>${u.blocked_open_attempts_today}</td><td>${u.realized_pnl_today}</td>
      </tr>`).join("") || '<tr><td colspan="9" class="muted">No users in scope</td></tr>';
    }
    async function load() {
      const token = byId("token").value.trim();
      if (!token) return;
      saveToken(token);
      const email = encodeURIComponent(byId("emailFilter").value.trim());
      const exchange = encodeURIComponent(byId("exchangeFilter").value || "ALL");
      const realOnly = encodeURIComponent(byId("realOnlyFilter").value || "true");
      const qs = `/ops/dashboard/summary?real_only=${realOnly}&email_contains=${email}&exchange=${exchange}`;
      const res = await fetch(qs, { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Dashboard request failed");
      fill(data);
      await loadRiskProfiles();
      await loadAdminUsers();
    }
    byId("load").addEventListener("click", async () => {
      try { await load(); } catch (e) { byId("stamp").textContent = String(e.message || e); setOverall("red"); }
    });
    byId("resetBtn").addEventListener("click", async () => {
      byId("emailFilter").value = "";
      byId("realOnlyFilter").value = "true";
      byId("exchangeFilter").value = "ALL";
      try { await load(); } catch (e) { byId("stamp").textContent = String(e.message || e); setOverall("red"); }
    });
    byId("rememberToken").addEventListener("change", () => {
      const token = byId("token").value.trim();
      saveToken(token);
    });
    byId("incidentBtn").addEventListener("click", () => {
      const repo = "https://github.com/Gonzalo-Giraldo/crypto-saas";
      const ts = new Date().toISOString();
      const title = encodeURIComponent(`[Ops Dashboard] Incident ${ts}`);
      const body = encodeURIComponent(`Opened from /ops/dashboard\n\n- Timestamp: ${ts}\n- Context: dashboard review\n`);
      window.open(`${repo}/issues/new?title=${title}&body=${body}`, "_blank");
    });
    byId("refreshUsersBtn").addEventListener("click", async () => {
      try {
        const keepId = selectedUserId();
        await loadAdminUsers(keepId);
        await runReadinessCheck(selectedUserId());
        setAdminMsg("Users refreshed.");
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("createUserBtn").addEventListener("click", async () => {
      try {
        const token = byId("token").value.trim();
        const email = byId("newUserEmail").value.trim();
        const password = byId("newUserPassword").value;
        if (!token) throw new Error("Token required");
        if (!email || !password) throw new Error("Email and password are required");
        await apiJson("/users", token, {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        byId("newUserPassword").value = "";
        await loadAdminUsers(selectedUserId());
        await runReadinessCheck(selectedUserId());
        setAdminMsg(`User created: ${email}`);
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("setRoleBtn").addEventListener("click", async () => {
      try {
        const token = byId("token").value.trim();
        const user = selectedUserObj();
        const role = byId("adminRoleSelect").value;
        if (!token) throw new Error("Token required");
        if (!user) throw new Error("Select a user first");
        await apiJson(`/users/${user.id}/role`, token, {
          method: "PATCH",
          body: JSON.stringify({ role }),
        });
        await loadAdminUsers(user.id);
        setAdminMsg(`Role updated for ${user.email}: ${role}`);
        await runReadinessCheck(user.id);
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("setEmailBtn").addEventListener("click", async () => {
      try {
        const token = byId("token").value.trim();
        const user = selectedUserObj();
        const email = byId("newEmailInput").value.trim();
        if (!token) throw new Error("Token required");
        if (!user) throw new Error("Select a user first");
        if (!email) throw new Error("New email is required");
        await apiJson(`/users/${user.id}/email`, token, {
          method: "PATCH",
          body: JSON.stringify({ email }),
        });
        byId("newEmailInput").value = "";
        await loadAdminUsers(user.id);
        setAdminMsg(`Email updated for user id ${user.id}`);
        await runReadinessCheck(user.id);
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("setRiskBtn").addEventListener("click", async () => {
      try {
        const token = byId("token").value.trim();
        const user = selectedUserObj();
        const profile_name = byId("adminRiskSelect").value;
        if (!token) throw new Error("Token required");
        if (!user) throw new Error("Select a user first");
        await apiJson(`/users/${user.id}/risk-profile`, token, {
          method: "PUT",
          body: JSON.stringify({ profile_name }),
        });
        await loadAdminUsers(user.id);
        setAdminMsg(`Risk profile updated for ${user.email}: ${profile_name}`);
        await runReadinessCheck(user.id);
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("clearRiskBtn").addEventListener("click", async () => {
      try {
        const token = byId("token").value.trim();
        const user = selectedUserObj();
        if (!token) throw new Error("Token required");
        if (!user) throw new Error("Select a user first");
        await apiJson(`/users/${user.id}/risk-profile`, token, {
          method: "PUT",
          body: JSON.stringify({ profile_name: null }),
        });
        await loadAdminUsers(user.id);
        setAdminMsg(`Risk override cleared for ${user.email}`);
        await runReadinessCheck(user.id);
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("setPasswordBtn").addEventListener("click", async () => {
      try {
        const token = byId("token").value.trim();
        const user = selectedUserObj();
        const new_password = byId("newPasswordInput").value;
        if (!token) throw new Error("Token required");
        if (!user) throw new Error("Select a user first");
        if (!new_password || new_password.length < 8) throw new Error("Password must be at least 8 characters");
        await apiJson(`/users/${user.id}/password`, token, {
          method: "PUT",
          body: JSON.stringify({ new_password }),
        });
        byId("newPasswordInput").value = "";
        setAdminMsg(`Password updated for ${user.email}`);
        await runReadinessCheck(user.id);
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("setSecretBtn").addEventListener("click", async () => {
      try {
        const token = byId("token").value.trim();
        const user = selectedUserObj();
        const exchange = byId("adminExchangeSelect").value;
        const api_key = byId("adminApiKey").value.trim();
        const api_secret = byId("adminApiSecret").value;
        if (!token) throw new Error("Token required");
        if (!user) throw new Error("Select a user first");
        if (!api_key || !api_secret) throw new Error("API key and API secret are required");
        await apiJson(`/users/${user.id}/exchange-secrets`, token, {
          method: "PUT",
          body: JSON.stringify({ exchange, api_key, api_secret }),
        });
        byId("adminApiSecret").value = "";
        setAdminMsg(`Secret saved for ${user.email} (${exchange})`);
        await runReadinessCheck(user.id);
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("deleteSecretBtn").addEventListener("click", async () => {
      try {
        const token = byId("token").value.trim();
        const user = selectedUserObj();
        const exchange = byId("adminExchangeSelect").value;
        if (!token) throw new Error("Token required");
        if (!user) throw new Error("Select a user first");
        await apiJson(`/users/${user.id}/exchange-secrets/${exchange}`, token, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        });
        setAdminMsg(`Secret deleted for ${user.email} (${exchange})`);
        await runReadinessCheck(user.id);
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("adminUserSelect").addEventListener("change", async () => {
      try {
        await runReadinessCheck(selectedUserId());
      } catch (e) {
        setAdminMsg(String(e.message || e), true);
      }
    });
    byId("loginBtn").addEventListener("click", async () => {
      try {
        const email = byId("loginEmail").value.trim();
        const password = byId("loginPassword").value;
        const otp = byId("loginOtp").value.trim();
        if (!email || !password) {
          throw new Error("Email and password are required");
        }
        localStorage.setItem(LOGIN_EMAIL_KEY, email);
        const body = new URLSearchParams();
        body.set("username", email);
        body.set("password", password);
        if (otp) body.set("otp", otp);
        const res = await fetch("/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: body.toString(),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Login failed");
        const token = data.access_token || "";
        if (!token) throw new Error("No token returned");
        byId("token").value = token;
        saveToken(token);
        byId("loginPassword").value = "";
        byId("loginOtp").value = "";
        await load();
      } catch (e) {
        byId("stamp").textContent = String(e.message || e);
        setOverall("red");
      }
    });
    setInterval(async () => {
      const token = byId("token").value.trim();
      if (!token) return;
      try { await load(); } catch (_) {}
    }, 60000);
    loadStoredToken();
  </script>
</body>
</html>
        """
    )
