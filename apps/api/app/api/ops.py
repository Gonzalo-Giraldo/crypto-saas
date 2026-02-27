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
    SecurityPostureOut,
    SecurityPostureSummaryOut,
    SecurityPostureUserOut,
)
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


def _is_real_user_email(email: str) -> bool:
    e = (email or "").lower()
    if e.startswith("smoke.") or e.startswith("disabled_"):
        return False
    if e.endswith("@example.com") or e.endswith("@example.invalid"):
        return False
    return True


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
    return _evaluate_pretrade_for_user(
        db=db,
        current_user=current_user,
        exchange="BINANCE",
        payload=payload,
    )


@router.post("/execution/pretrade/ibkr/check", response_model=PretradeCheckOut)
def pretrade_ibkr_check(
    payload: PretradeCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _evaluate_pretrade_for_user(
        db=db,
        current_user=current_user,
        exchange="IBKR",
        payload=payload,
    )


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


@router.get("/security/posture", response_model=SecurityPostureOut)
def security_posture(
    real_only: bool = False,
    max_secret_age_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
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

        oldest_days: int | None = None
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
