from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from apps.api.app.api.deps import get_current_user, require_any_role, require_role
from apps.api.app.db.session import get_db
from apps.api.app.models.audit_log import AuditLog
from apps.api.app.models.daily_risk import DailyRiskState
from apps.api.app.models.exchange_secret import ExchangeSecret
from apps.api.app.models.idempotency_key import IdempotencyKey
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
    IdempotencyStatsOut,
    IdempotencyCleanupOut,
    BackofficeSummaryOut,
    BackofficeUserOut,
)
from apps.api.app.core.config import settings
from apps.api.app.models.user import User
from apps.api.app.schemas.audit import AuditExportMetaOut, AuditExportOut, AuditOut
from apps.api.app.core.time import today_colombia
from apps.api.app.services.audit import log_audit_event
from apps.api.app.services.key_rotation import reencrypt_exchange_secrets
from apps.api.app.services.risk_profiles import resolve_risk_profile
from apps.api.app.services.idempotency import (
    cleanup_old_idempotency_keys,
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


def _tenant_id(user: User) -> str:
    return (user.tenant_id or "default")


def _build_security_posture_rows(
    db: Session,
    *,
    tenant_id: Optional[str],
    real_only: bool,
    max_secret_age_days: int,
):
    now = datetime.now(timezone.utc)
    users_q = select(User).order_by(User.email.asc())
    if tenant_id:
        users_q = users_q.where(User.tenant_id == tenant_id)
    users = db.execute(users_q).scalars().all()
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

        if user.role in {"admin", "operator", "viewer", "trader"} and not two_factor_enabled:
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


@router.get("/backoffice/summary", response_model=BackofficeSummaryOut)
def backoffice_summary(
    real_only: bool = True,
    max_secret_age_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role("admin", "operator", "viewer")),
):
    tenant = _tenant_id(current_user)
    now, posture_rows, missing_2fa, stale_secrets = _build_security_posture_rows(
        db,
        tenant_id=tenant,
        real_only=real_only,
        max_secret_age_days=max_secret_age_days,
    )
    _ = now
    counts = {"admin": 0, "operator": 0, "viewer": 0, "trader": 0, "disabled": 0}
    for row in posture_rows:
        role = (row.role or "").lower()
        if role in counts:
            counts[role] += 1

    return BackofficeSummaryOut(
        tenant_id=tenant,
        total_users=len(posture_rows),
        admins=counts["admin"],
        operators=counts["operator"],
        viewers=counts["viewer"],
        traders=counts["trader"],
        disabled=counts["disabled"],
        users_missing_2fa=missing_2fa,
        users_with_stale_secrets=stale_secrets,
    )


@router.get("/backoffice/users", response_model=list[BackofficeUserOut])
def backoffice_users(
    real_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role("admin", "operator", "viewer")),
):
    tenant = _tenant_id(current_user)
    users = db.execute(
        select(User)
        .where(User.tenant_id == tenant)
        .order_by(User.email.asc())
    ).scalars().all()

    out = []
    for u in users:
        if real_only and not _is_real_user_email(u.email):
            continue

        user_2fa = (
            db.execute(select(UserTwoFactor).where(UserTwoFactor.user_id == u.id))
            .scalar_one_or_none()
        )
        two_factor_enabled = bool(user_2fa and user_2fa.enabled)

        secrets = db.execute(
            select(ExchangeSecret.exchange).where(ExchangeSecret.user_id == u.id)
        ).all()
        secret_set = {row[0] for row in secrets}
        binance_secret = "BINANCE" in secret_set
        ibkr_secret = "IBKR" in secret_set

        assignment_rows = db.execute(
            select(StrategyAssignment.exchange, StrategyAssignment.enabled).where(
                StrategyAssignment.user_id == u.id
            )
        ).all()
        enabled_map = {exchange: bool(enabled) for exchange, enabled in assignment_rows}
        binance_enabled = bool(enabled_map.get("BINANCE", False))
        ibkr_enabled = bool(enabled_map.get("IBKR", False))

        checks = []
        if u.role in {"admin", "operator", "viewer", "trader"}:
            checks.append(two_factor_enabled)
        if binance_enabled:
            checks.append(binance_secret)
        if ibkr_enabled:
            checks.append(ibkr_secret)
        readiness = "READY" if all(checks) else "MISSING"

        out.append(
            BackofficeUserOut(
                user_id=u.id,
                email=u.email,
                role=u.role,
                two_factor_enabled=two_factor_enabled,
                binance_enabled=binance_enabled,
                ibkr_enabled=ibkr_enabled,
                binance_secret_configured=binance_secret,
                ibkr_secret_configured=ibkr_secret,
                readiness=readiness,
            )
        )
    return out


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


@router.get("/admin/idempotency/stats", response_model=IdempotencyStatsOut)
def get_idempotency_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    total = int(
        db.execute(select(func.count()).select_from(IdempotencyKey)).scalar_one()
    )
    oldest = db.execute(select(func.min(IdempotencyKey.created_at))).scalar_one_or_none()
    newest = db.execute(select(func.max(IdempotencyKey.created_at))).scalar_one_or_none()
    log_audit_event(
        db,
        action="security.idempotency.stats.read",
        user_id=current_user.id,
        entity_type="security",
        details={"records_total": total},
    )
    db.commit()
    return IdempotencyStatsOut(
        records_total=total,
        max_age_days=int(settings.IDEMPOTENCY_KEY_MAX_AGE_DAYS),
        oldest_record_at=oldest.isoformat() if oldest else None,
        newest_record_at=newest.isoformat() if newest else None,
    )


@router.post("/admin/idempotency/cleanup", response_model=IdempotencyCleanupOut)
def post_idempotency_cleanup(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    deleted = cleanup_old_idempotency_keys(db)
    log_audit_event(
        db,
        action="security.idempotency.cleanup",
        user_id=current_user.id,
        entity_type="security",
        details={
            "deleted": deleted,
            "max_age_days": int(settings.IDEMPOTENCY_KEY_MAX_AGE_DAYS),
        },
    )
    db.commit()
    return IdempotencyCleanupOut(
        deleted=int(deleted),
        max_age_days=int(settings.IDEMPOTENCY_KEY_MAX_AGE_DAYS),
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
    tenant_ids = (
        select(User.id).where(User.tenant_id == _tenant_id(current_user))
    )
    rows = (
        db.execute(
            select(AuditLog)
            .where(AuditLog.user_id.in_(tenant_ids))
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return rows


@router.get("/admin/audit/export", response_model=AuditExportOut)
def export_audit(
    limit: int = 500,
    from_iso: Optional[str] = None,
    to_iso: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    tenant = _tenant_id(current_user)
    tenant_ids = select(User.id).where(User.tenant_id == tenant)

    q = select(AuditLog).where(AuditLog.user_id.in_(tenant_ids))
    if from_iso:
        try:
            from_dt = datetime.fromisoformat(from_iso.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid from_iso")
        q = q.where(AuditLog.created_at >= from_dt)
    if to_iso:
        try:
            to_dt = datetime.fromisoformat(to_iso.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid to_iso")
        q = q.where(AuditLog.created_at <= to_dt)

    rows = (
        db.execute(
            q.order_by(AuditLog.created_at.desc()).limit(max(1, min(limit, 5000)))
        )
        .scalars()
        .all()
    )
    records = [AuditOut.model_validate(r) for r in rows]
    meta = AuditExportMetaOut(
        exported_at=datetime.now(timezone.utc).isoformat(),
        exported_by=current_user.email,
        tenant_id=tenant,
        limit=max(1, min(limit, 5000)),
        from_iso=from_iso,
        to_iso=to_iso,
        records_count=len(records),
        algorithm="sha256+hmac-sha256",
    )

    payload = {
        "meta": meta.model_dump(),
        "records": [r.model_dump(mode="json") for r in records],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    payload_sha256 = hashlib.sha256(canonical).hexdigest()
    signing_key = (settings.AUDIT_EXPORT_SIGNING_KEY or settings.SECRET_KEY).encode("utf-8")
    signature = hmac.new(signing_key, canonical, hashlib.sha256).hexdigest()

    log_audit_event(
        db,
        action="security.audit.export",
        user_id=current_user.id,
        entity_type="security",
        details={
            "tenant_id": tenant,
            "records_count": len(records),
            "from_iso": from_iso,
            "to_iso": to_iso,
            "limit": max(1, min(limit, 5000)),
        },
    )
    db.commit()

    return AuditExportOut(
        meta=meta,
        records=records,
        payload_sha256=payload_sha256,
        signature_hmac_sha256=signature,
    )


@router.get("/risk/daily-compare")
def daily_risk_compare(
    real_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    today = today_colombia()
    users = db.execute(
        select(User)
        .where(User.tenant_id == _tenant_id(current_user))
        .order_by(User.email.asc())
    ).scalars().all()
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
        select(User).where(
            User.email == payload.user_email,
            User.tenant_id == _tenant_id(current_user),
        )
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
        .where(User.tenant_id == _tenant_id(current_user))
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
        tenant_id=_tenant_id(current_user),
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
        select(User)
        .where(
            User.email.like("smoke.%"),
            User.tenant_id == _tenant_id(current_user),
        )
        .order_by(User.email.asc())
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
        tenant_id=_tenant_id(current_user),
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

    users = db.execute(
        select(User)
        .where(User.tenant_id == _tenant_id(current_user))
        .order_by(User.email.asc())
    ).scalars().all()
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


@router.get("/admin/snapshot/daily")
def admin_snapshot_daily(
    real_only: bool = True,
    max_secret_age_days: int = 30,
    recent_hours: int = 24,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    dashboard = dashboard_summary(
        real_only=real_only,
        max_secret_age_days=max_secret_age_days,
        recent_hours=recent_hours,
        email_contains=None,
        exchange="ALL",
        include_service_users=False,
        db=db,
        current_user=current_user,
    )
    backoffice_sum = backoffice_summary(
        real_only=real_only,
        max_secret_age_days=max_secret_age_days,
        db=db,
        current_user=current_user,
    )
    backoffice_usr = backoffice_users(
        real_only=real_only,
        db=db,
        current_user=current_user,
    )
    posture = security_posture(
        real_only=real_only,
        max_secret_age_days=max_secret_age_days,
        db=db,
        current_user=current_user,
    )
    risk = daily_risk_compare(
        real_only=real_only,
        db=db,
        current_user=current_user,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_for": current_user.email,
        "real_only": real_only,
        "dashboard": dashboard,
        "backoffice_summary": backoffice_sum,
        "backoffice_users": backoffice_usr,
        "security_posture": posture,
        "risk_daily_compare": risk,
    }


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


@router.get("/console", response_class=HTMLResponse)
def ops_console_page():
    return HTMLResponse(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Ops Console v1</title>
  <style>
    :root {
      --bg:#f3f5f9; --card:#ffffff; --ink:#122033; --muted:#607086;
      --line:#d7e0eb; --ok:#147a46; --warn:#9a5a00; --bad:#b42318; --brand:#0f5fd2;
    }
    * { box-sizing:border-box; }
    body { margin:0; font-family: "Segoe UI", Tahoma, sans-serif; background: radial-gradient(1200px 500px at 10% -5%, #d9e9ff, transparent 50%), var(--bg); color:var(--ink); }
    .shell { max-width:1200px; margin:20px auto; padding:0 14px 26px; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:14px; margin-bottom:12px; }
    h1 { margin:0 0 6px; font-size:28px; }
    .muted { color:var(--muted); font-size:13px; }
    .row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:8px; }
    .kpi { border:1px solid var(--line); border-radius:10px; padding:10px; }
    .kpi .v { font-size:24px; font-weight:700; }
    input, select { border:1px solid var(--line); border-radius:10px; padding:10px 12px; background:#fff; min-width:120px; }
    input[type="password"] { min-width:180px; }
    button { border:0; border-radius:10px; padding:10px 14px; font-weight:700; cursor:pointer; background:var(--brand); color:#fff; }
    .ghost { background:#edf3fc; color:#0c57c4; border:1px solid #bbd0f3; }
    .badge { display:inline-block; padding:3px 9px; border-radius:999px; font-weight:700; font-size:12px; color:#fff; }
    .green { background:var(--ok); } .yellow { background:var(--warn); } .red { background:var(--bad); }
    .tabs { display:flex; gap:8px; margin-top:10px; }
    .tab { background:#eef3fb; color:#24579f; border:1px solid #bfd1ee; border-radius:10px; padding:8px 12px; font-weight:700; cursor:pointer; }
    .tab.active { background:#0f5fd2; color:#fff; border-color:#0f5fd2; }
    .panel { display:none; }
    .panel.active { display:block; }
    table { width:100%; border-collapse:collapse; }
    th,td { border-bottom:1px solid var(--line); text-align:left; padding:8px 6px; font-size:13px; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size:12px; }
    .mini { padding:6px 8px; border-radius:8px; font-size:12px; }
  </style>
</head>
<body>
  <div class="shell">
    <div class="card">
      <h1>Ops Console v1</h1>
      <div class="muted">Sprint B: Login + Home + Backoffice user management</div>
      <div class="row" style="margin-top:10px">
        <input id="email" placeholder="email" />
        <input id="password" type="password" placeholder="password" />
        <input id="otp" placeholder="otp (if required)" style="max-width:170px" />
        <button id="loginBtn">Login</button>
        <button id="refreshSessionBtn" class="ghost">Refresh Session</button>
        <button id="logoutBtn" class="ghost">Logout</button>
      </div>
      <div class="row" style="margin-top:8px">
        <input id="token" placeholder="or paste bearer token" style="min-width:420px;max-width:100%" />
        <button id="loadBtn" class="ghost">Load</button>
      </div>
      <div id="sessionInfo" class="muted" style="margin-top:8px">No active session</div>
    </div>

    <div class="card">
      <div class="tabs">
        <button class="tab active" data-tab="home">Home</button>
        <button class="tab" data-tab="backoffice">Backoffice</button>
      </div>
    </div>

    <div id="home" class="panel active">
      <div class="card">
        <div class="row"><strong>Overall:</strong> <span id="overall" class="badge yellow">unknown</span></div>
        <div class="grid" style="margin-top:10px">
          <div class="kpi"><div class="muted">Users in scope</div><div id="k_users" class="v">-</div></div>
          <div class="kpi"><div class="muted">Missing 2FA</div><div id="k_2fa" class="v">-</div></div>
          <div class="kpi"><div class="muted">Stale secrets</div><div id="k_stale" class="v">-</div></div>
          <div class="kpi"><div class="muted">Trades today</div><div id="k_trades" class="v">-</div></div>
          <div class="kpi"><div class="muted">Open positions</div><div id="k_open" class="v">-</div></div>
          <div class="kpi"><div class="muted">Blocked opens</div><div id="k_blocked" class="v">-</div></div>
        </div>
        <div id="homeMsg" class="muted" style="margin-top:8px">Load data to start.</div>
        <div id="tradingCtl" class="card" style="margin-top:10px;display:none">
          <div class="row">
            <strong>Global Trading Control</strong>
            <span id="tradingCtlBadge" class="badge yellow">unknown</span>
          </div>
          <div class="row" style="margin-top:8px">
            <input id="tradingCtlReason" placeholder="reason (required to disable)" style="min-width:320px" />
            <button id="tradingCtlDisableBtn" class="mini">Disable</button>
            <button id="tradingCtlEnableBtn" class="ghost mini">Enable</button>
            <button id="tradingCtlRefreshBtn" class="ghost mini">Refresh</button>
          </div>
          <div id="tradingCtlMsg" class="muted" style="margin-top:6px">No data</div>
        </div>
        <div id="maintCtl" class="card" style="margin-top:10px;display:none">
          <div class="row">
            <strong>Admin Maintenance</strong>
          </div>
          <div class="row" style="margin-top:8px">
            <input id="cleanupDays" type="number" min="1" value="14" style="max-width:120px" />
            <button id="cleanupDryBtn" class="ghost mini">Cleanup dry-run</button>
            <button id="cleanupApplyBtn" class="mini">Cleanup apply</button>
          </div>
          <div class="row" style="margin-top:8px">
            <button id="idemStatsBtn" class="ghost mini">Idempotency stats</button>
            <button id="idemCleanupBtn" class="ghost mini">Idempotency cleanup</button>
          </div>
          <div id="maintMsg" class="muted" style="margin-top:6px">No data</div>
        </div>
        <div id="incidentAuditCtl" class="card" style="margin-top:10px;display:none">
          <div class="row">
            <strong>Incident & Audit</strong>
          </div>
          <div class="row" style="margin-top:8px">
            <input id="incidentTitle" placeholder="incident title (optional)" style="min-width:320px" />
            <button id="openIncidentBtn" class="mini">Open Incident</button>
          </div>
          <div class="row" style="margin-top:8px">
            <input id="auditLimit" type="number" min="1" max="200" value="20" style="max-width:120px" />
            <button id="auditLoadBtn" class="ghost mini">Load audit</button>
            <button id="auditExportBtn" class="ghost mini">Export signed JSON</button>
          </div>
          <div id="incidentAuditMsg" class="muted" style="margin-top:6px">No data</div>
          <table style="margin-top:8px">
            <thead>
              <tr><th>When</th><th>User</th><th>Action</th><th>Entity</th></tr>
            </thead>
            <tbody id="auditBody">
              <tr><td colspan="4" class="muted">No audit loaded</td></tr>
            </tbody>
          </table>
        </div>
        <div id="execLabCtl" class="card" style="margin-top:10px;display:none">
          <div class="row">
            <strong>Execution Lab</strong>
            <span class="muted">Runs with current signed-in user token</span>
          </div>
          <div class="row" style="margin-top:8px">
            <select id="execExchange">
              <option value="BINANCE">BINANCE</option>
              <option value="IBKR">IBKR</option>
            </select>
            <input id="execSymbol" placeholder="symbol" value="BTCUSDT" style="max-width:160px" />
            <select id="execSide">
              <option value="BUY">BUY</option>
              <option value="SELL">SELL</option>
            </select>
            <input id="execQty" type="number" step="0.0001" value="0.01" style="max-width:120px" />
          </div>
          <div class="row" style="margin-top:8px">
            <button id="execPretradeBtn" class="ghost mini">Pretrade check</button>
            <button id="execExitBtn" class="ghost mini">Exit check</button>
            <button id="execTestOrderBtn" class="mini">Test order</button>
          </div>
          <div id="execLabMsg" class="muted" style="margin-top:6px">No data</div>
          <pre id="execLabOut" class="mono" style="white-space:pre-wrap;background:#f7f9fc;border:1px solid var(--line);border-radius:10px;padding:10px;max-height:280px;overflow:auto;">{}</pre>
        </div>
        <div id="snapshotCtl" class="card" style="margin-top:10px;display:none">
          <div class="row">
            <strong>Daily Snapshot</strong>
            <span class="muted">One-file operational snapshot</span>
          </div>
          <div class="row" style="margin-top:8px">
            <button id="snapshotBuildBtn" class="ghost mini">Build snapshot</button>
            <button id="snapshotDownloadBtn" class="mini">Download JSON</button>
          </div>
          <div id="snapshotMsg" class="muted" style="margin-top:6px">No snapshot built</div>
        </div>
      </div>
    </div>

    <div id="backoffice" class="panel">
      <div class="card">
        <strong>Backoffice Summary</strong>
        <table style="margin-top:8px">
          <tbody id="boSummary">
            <tr><td class="muted">No data</td></tr>
          </tbody>
        </table>
      </div>
      <div class="card">
        <strong>Backoffice Users</strong>
        <div id="boMsg" class="muted" style="margin-top:6px">Readonly for operator/viewer. Editable for admin.</div>
        <div class="row" style="margin-top:8px">
          <input id="boEmailFilter" placeholder="email contains" style="min-width:220px" />
          <select id="boRoleFilter">
            <option value="ALL">All roles</option>
            <option value="admin">admin</option>
            <option value="operator">operator</option>
            <option value="viewer">viewer</option>
            <option value="trader">trader</option>
            <option value="disabled">disabled</option>
          </select>
          <button id="boApplyFilterBtn" class="ghost mini">Apply</button>
          <button id="boResetFilterBtn" class="ghost mini">Reset</button>
        </div>
        <table style="margin-top:8px">
          <thead>
            <tr><th>Email</th><th>Role</th><th>Risk profile</th><th>2FA</th><th>BINANCE</th><th>IBKR</th><th>Readiness</th><th>Action</th></tr>
          </thead>
          <tbody id="boUsers">
            <tr><td colspan="8" class="muted">No data</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
  <script>
    const byId = (id) => document.getElementById(id);
    const STORE_TOKEN = "ops_console_token";
    const STORE_EMAIL = "ops_console_email";
    const STORE_REFRESH = "ops_console_refresh";
    const USER_ROLES = ["admin", "operator", "viewer", "trader", "disabled"];
    const state = {
      me: null,
      token: "",
      riskProfiles: [],
      usersById: {},
      assignments: {},
      tradingControl: null,
      backofficeUsers: [],
      refreshToken: "",
      snapshotData: null,
    };

    function esc(v) {
      return String(v ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function setOverall(v) {
      const el = byId("overall");
      el.textContent = v || "unknown";
      el.className = "badge " + (v === "green" ? "green" : v === "red" ? "red" : "yellow");
    }

    function setBoMsg(msg, bad=false) {
      const el = byId("boMsg");
      el.textContent = msg;
      el.style.color = bad ? "var(--bad)" : "var(--muted)";
    }

    function setTradingCtlMsg(msg, bad=false) {
      const el = byId("tradingCtlMsg");
      if (!el) return;
      el.textContent = msg;
      el.style.color = bad ? "var(--bad)" : "var(--muted)";
    }

    function setMaintMsg(msg, bad=false) {
      const el = byId("maintMsg");
      if (!el) return;
      el.textContent = msg;
      el.style.color = bad ? "var(--bad)" : "var(--muted)";
    }

    function setIncidentAuditMsg(msg, bad=false) {
      const el = byId("incidentAuditMsg");
      if (!el) return;
      el.textContent = msg;
      el.style.color = bad ? "var(--bad)" : "var(--muted)";
    }

    function setExecLabMsg(msg, bad=false) {
      const el = byId("execLabMsg");
      if (!el) return;
      el.textContent = msg;
      el.style.color = bad ? "var(--bad)" : "var(--muted)";
    }

    function setExecLabOut(payload) {
      byId("execLabOut").textContent = JSON.stringify(payload || {}, null, 2);
    }

    function setSnapshotMsg(msg, bad=false) {
      const el = byId("snapshotMsg");
      if (!el) return;
      el.textContent = msg;
      el.style.color = bad ? "var(--bad)" : "var(--muted)";
    }

    function renderTradingControl(control, canEdit) {
      const wrap = byId("tradingCtl");
      if (!wrap) return;
      if (!canEdit) {
        wrap.style.display = "none";
        return;
      }
      wrap.style.display = "block";
      const badge = byId("tradingCtlBadge");
      const enabled = Boolean(control && control.trading_enabled);
      badge.textContent = enabled ? "enabled" : "disabled";
      badge.className = "badge " + (enabled ? "green" : "red");
      const by = control && control.updated_by ? control.updated_by : "unknown";
      const reason = control && control.reason ? control.reason : "-";
      setTradingCtlMsg(`updated_by=${by} | reason=${reason}`);
    }

    function renderMaintenance(canEdit) {
      const wrap = byId("maintCtl");
      if (!wrap) return;
      wrap.style.display = canEdit ? "block" : "none";
      if (canEdit) setMaintMsg("Ready");
    }

    function renderIncidentAudit(canEdit) {
      const wrap = byId("incidentAuditCtl");
      if (!wrap) return;
      wrap.style.display = canEdit ? "block" : "none";
      if (canEdit) setIncidentAuditMsg("Ready");
      if (!canEdit) byId("auditBody").innerHTML = '<tr><td colspan="4" class="muted">No audit loaded</td></tr>';
    }

    function renderExecLab(canUse) {
      const wrap = byId("execLabCtl");
      if (!wrap) return;
      wrap.style.display = canUse ? "block" : "none";
      if (canUse) {
        setExecLabMsg("Ready");
      } else {
        setExecLabOut({});
      }
    }

    function renderSnapshot(canUse) {
      const wrap = byId("snapshotCtl");
      if (!wrap) return;
      wrap.style.display = canUse ? "block" : "none";
      if (canUse) setSnapshotMsg("Ready");
    }

    function authHeaders(token, isForm=false) {
      if (isForm) return { "Content-Type": "application/x-www-form-urlencoded" };
      return { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" };
    }

    async function api(path, opts={}) {
      const res = await fetch(path, opts);
      const contentType = res.headers.get("content-type") || "";
      const data = contentType.includes("application/json") ? await res.json() : { detail: await res.text() };
      if (!res.ok) throw new Error(data.detail || `${res.status} ${path}`);
      return data;
    }

    async function login() {
      const email = byId("email").value.trim();
      const password = byId("password").value;
      const otp = byId("otp").value.trim();
      if (!email || !password) throw new Error("Email and password required");
      const form = new URLSearchParams();
      form.set("username", email);
      form.set("password", password);
      if (otp) form.set("otp", otp);
      const data = await api("/auth/login", {
        method: "POST",
        headers: authHeaders("", true),
        body: form.toString(),
      });
      const token = data.access_token || "";
      const refresh = data.refresh_token || "";
      if (!token) throw new Error("No access token in response");
      byId("token").value = token;
      localStorage.setItem(STORE_TOKEN, token);
      if (refresh) localStorage.setItem(STORE_REFRESH, refresh);
      localStorage.setItem(STORE_EMAIL, email);
      state.refreshToken = refresh;
      byId("password").value = "";
      byId("otp").value = "";
      await loadAll();
    }

    async function logout() {
      try {
        if (state.token && state.refreshToken) {
          await api("/auth/logout", {
            method: "POST",
            headers: { Authorization: `Bearer ${state.token}`, "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: state.refreshToken }),
          });
        }
      } catch (_) {
        // Ignore logout transport errors and clear local session anyway.
      }
      byId("token").value = "";
      localStorage.removeItem(STORE_TOKEN);
      localStorage.removeItem(STORE_REFRESH);
      byId("sessionInfo").textContent = "No active session";
      setOverall("unknown");
      byId("boSummary").innerHTML = '<tr><td class="muted">No data</td></tr>';
      byId("boUsers").innerHTML = '<tr><td colspan="8" class="muted">No data</td></tr>';
      byId("homeMsg").textContent = "Logged out";
      state.me = null;
      state.token = "";
      state.riskProfiles = [];
      state.usersById = {};
      state.assignments = {};
      state.tradingControl = null;
      state.backofficeUsers = [];
      state.refreshToken = "";
      state.snapshotData = null;
      renderTradingControl(null, false);
      renderMaintenance(false);
      renderIncidentAudit(false);
      renderExecLab(false);
      renderSnapshot(false);
    }

    async function refreshSession() {
      const refresh = state.refreshToken || localStorage.getItem(STORE_REFRESH) || "";
      if (!refresh) throw new Error("No refresh token available. Login again.");
      const out = await api("/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      const nextAccess = out.access_token || "";
      const nextRefresh = out.refresh_token || "";
      if (!nextAccess || !nextRefresh) throw new Error("Refresh response missing tokens");
      state.refreshToken = nextRefresh;
      state.token = nextAccess;
      byId("token").value = nextAccess;
      localStorage.setItem(STORE_TOKEN, nextAccess);
      localStorage.setItem(STORE_REFRESH, nextRefresh);
      await loadAll();
    }

    function fillHome(d) {
      setOverall(d.overall_status);
      byId("k_users").textContent = d.security.total_users;
      byId("k_2fa").textContent = d.security.users_missing_2fa;
      byId("k_stale").textContent = d.security.users_with_stale_secrets;
      byId("k_trades").textContent = d.operations.trades_today_total;
      byId("k_open").textContent = d.operations.open_positions_total;
      byId("k_blocked").textContent = d.operations.blocked_open_attempts_total;
      byId("homeMsg").textContent = `Generated ${d.generated_at} | Day ${d.day} | For ${d.generated_for}`;
    }

    function fillBackofficeSummary(s) {
      byId("boSummary").innerHTML = `
        <tr><td><strong>Tenant</strong></td><td class="mono">${s.tenant_id}</td></tr>
        <tr><td><strong>Total users</strong></td><td>${s.total_users}</td></tr>
        <tr><td><strong>Admins/Operators/Viewers/Traders</strong></td><td>${s.admins}/${s.operators}/${s.viewers}/${s.traders}</td></tr>
        <tr><td><strong>Disabled</strong></td><td>${s.disabled}</td></tr>
        <tr><td><strong>Missing 2FA</strong></td><td>${s.users_missing_2fa}</td></tr>
        <tr><td><strong>Stale secrets</strong></td><td>${s.users_with_stale_secrets}</td></tr>`;
    }

    function _options(values, selected) {
      return values.map((v) => `<option value="${esc(v)}" ${v === selected ? "selected" : ""}>${esc(v)}</option>`).join("");
    }

    function assignmentFor(userEmail, exchange) {
      const k = `${(userEmail || "").toLowerCase()}|${exchange}`;
      return state.assignments[k] || null;
    }

    function filteredBackofficeUsers() {
      const rows = state.backofficeUsers || [];
      const emailContains = (byId("boEmailFilter").value || "").trim().toLowerCase();
      const roleFilter = (byId("boRoleFilter").value || "ALL").trim().toLowerCase();
      return rows.filter((u) => {
        const okEmail = !emailContains || String(u.email || "").toLowerCase().includes(emailContains);
        const role = (state.usersById[u.user_id]?.role || u.role || "").toLowerCase();
        const okRole = roleFilter === "all" || role === roleFilter;
        return okEmail && okRole;
      });
    }

    function renderBackofficeUsersFromFilter() {
      fillBackofficeUsers(filteredBackofficeUsers());
    }

    function fillBackofficeUsers(rows) {
      const canEdit = state.me && state.me.role === "admin";
      const riskProfiles = state.riskProfiles || [];
      const out = (rows || []).map((u) => {
        const extra = state.usersById[u.user_id] || {};
        const role = extra.role || u.role || "trader";
        const risk = extra.risk_profile || "model2_conservador_productivo";
        const roleCell = canEdit
          ? `<select id="role_${u.user_id}">${_options(USER_ROLES, role)}</select>`
          : esc(role);
        const riskCell = canEdit
          ? `<select id="risk_${u.user_id}">${_options(riskProfiles, risk)}</select>`
          : esc(risk);
        const aBinance = assignmentFor(u.email, "BINANCE");
        const aIbkr = assignmentFor(u.email, "IBKR");
        const binanceCurrent = aBinance ? Boolean(aBinance.enabled) : Boolean(u.binance_enabled);
        const ibkrCurrent = aIbkr ? Boolean(aIbkr.enabled) : Boolean(u.ibkr_enabled);
        const binanceStrategy = (aBinance && aBinance.strategy_id) ? aBinance.strategy_id : "SWING_V1";
        const ibkrStrategy = (aIbkr && aIbkr.strategy_id) ? aIbkr.strategy_id : "SWING_V1";
        const actionCell = canEdit
          ? `
            <div class="row">
              <button class="save-user-btn ghost mini" data-user-id="${esc(u.user_id)}">Save</button>
              <button class="set-pass-btn ghost mini" data-user-id="${esc(u.user_id)}">Set password</button>
              <button class="reset-2fa-btn ghost mini" data-user-id="${esc(u.user_id)}">Reset 2FA</button>
              <button class="readiness-btn ghost mini" data-user-id="${esc(u.user_id)}">Readiness</button>
            </div>
            <div class="row" style="margin-top:6px">
              <button class="toggle-ex-btn ghost mini" data-user-email="${esc(u.email)}" data-exchange="BINANCE" data-next-enabled="${binanceCurrent ? "false" : "true"}" data-strategy-id="${esc(binanceStrategy)}">BINANCE ${binanceCurrent ? "off" : "on"}</button>
              <button class="toggle-ex-btn ghost mini" data-user-email="${esc(u.email)}" data-exchange="IBKR" data-next-enabled="${ibkrCurrent ? "false" : "true"}" data-strategy-id="${esc(ibkrStrategy)}">IBKR ${ibkrCurrent ? "off" : "on"}</button>
            </div>
            <div class="row" style="margin-top:6px">
              <button class="seed-secret-btn ghost mini" data-user-id="${esc(u.user_id)}" data-exchange="BINANCE">Set BINANCE secret</button>
              <button class="del-secret-btn ghost mini" data-user-id="${esc(u.user_id)}" data-exchange="BINANCE">Del BINANCE secret</button>
            </div>
            <div class="row" style="margin-top:6px">
              <button class="seed-secret-btn ghost mini" data-user-id="${esc(u.user_id)}" data-exchange="IBKR">Set IBKR secret</button>
              <button class="del-secret-btn ghost mini" data-user-id="${esc(u.user_id)}" data-exchange="IBKR">Del IBKR secret</button>
            </div>
          `
          : '<span class="muted">readonly</span>';
        return `
        <tr>
          <td>${esc(u.email)}</td>
          <td>${roleCell}</td>
          <td>${riskCell}</td>
          <td>${u.two_factor_enabled ? "yes" : "no"}</td>
          <td>${u.binance_enabled ? (u.binance_secret_configured ? "enabled+secret" : "enabled/no secret") : "off"}</td>
          <td>${u.ibkr_enabled ? (u.ibkr_secret_configured ? "enabled+secret" : "enabled/no secret") : "off"}</td>
          <td><span class="badge ${u.readiness === "READY" ? "green" : "red"}">${u.readiness}</span></td>
          <td>${actionCell}</td>
        </tr>
      `;
      }).join("");
      byId("boUsers").innerHTML = out || '<tr><td colspan="8" class="muted">No users in scope</td></tr>';
      if (canEdit) {
        document.querySelectorAll(".save-user-btn").forEach((btn) => {
          btn.addEventListener("click", async () => {
            const userId = btn.getAttribute("data-user-id");
            const roleSel = byId(`role_${userId}`);
            const riskSel = byId(`risk_${userId}`);
            if (!userId || !roleSel || !riskSel) return;
            const nextRole = roleSel.value;
            const nextRisk = riskSel.value;
            btn.disabled = true;
            setBoMsg("Saving user update...");
            try {
              await api(`/users/${userId}/role`, {
                method: "PATCH",
                headers: { Authorization: `Bearer ${state.token}`, "Content-Type": "application/json" },
                body: JSON.stringify({ role: nextRole }),
              });
              await api(`/users/${userId}/risk-profile`, {
                method: "PUT",
                headers: { Authorization: `Bearer ${state.token}`, "Content-Type": "application/json" },
                body: JSON.stringify({ profile_name: nextRisk }),
              });
              setBoMsg(`User updated: ${userId}`);
              await loadAll();
            } catch (e) {
              setBoMsg(`Update failed: ${String(e.message || e)}`, true);
              btn.disabled = false;
            }
          });
        });
        document.querySelectorAll(".set-pass-btn").forEach((btn) => {
          btn.addEventListener("click", async () => {
            const userId = btn.getAttribute("data-user-id");
            if (!userId) return;
            const user = state.usersById[userId];
            const nextPassword = prompt(`New password for ${user ? user.email : userId} (min 8 chars):`);
            if (nextPassword === null) return;
            if (!nextPassword || nextPassword.length < 8) {
              setBoMsg("Password must be at least 8 characters", true);
              return;
            }
            btn.disabled = true;
            setBoMsg("Updating password...");
            try {
              await api(`/users/${userId}/password`, {
                method: "PUT",
                headers: { Authorization: `Bearer ${state.token}`, "Content-Type": "application/json" },
                body: JSON.stringify({ new_password: nextPassword }),
              });
              setBoMsg(`Password updated for ${user ? user.email : userId}`);
            } catch (e) {
              setBoMsg(`Password update failed: ${String(e.message || e)}`, true);
              btn.disabled = false;
            }
          });
        });
        document.querySelectorAll(".reset-2fa-btn").forEach((btn) => {
          btn.addEventListener("click", async () => {
            const userId = btn.getAttribute("data-user-id");
            if (!userId) return;
            const user = state.usersById[userId];
            const ok = confirm(`Reset 2FA for ${user ? user.email : userId}?`);
            if (!ok) return;
            btn.disabled = true;
            setBoMsg("Resetting 2FA...");
            try {
              const out = await api(`/users/${userId}/2fa/reset`, {
                method: "POST",
                headers: { Authorization: `Bearer ${state.token}` },
              });
              setBoMsg(`2FA reset ok for ${out.email}`);
              alert(
                `2FA reset for ${out.email}\\n\\n` +
                `SECRET: ${out.secret}\\n\\n` +
                `OTPAUTH URI: ${out.otpauth_uri}\\n\\n` +
                `Add this as a NEW account in Authenticator.`
              );
              await loadAll();
            } catch (e) {
              setBoMsg(`2FA reset failed: ${String(e.message || e)}`, true);
              btn.disabled = false;
            }
          });
        });
        document.querySelectorAll(".readiness-btn").forEach((btn) => {
          btn.addEventListener("click", async () => {
            const userId = btn.getAttribute("data-user-id");
            if (!userId) return;
            const user = state.usersById[userId];
            btn.disabled = true;
            setBoMsg("Loading readiness...");
            try {
              const readiness = await api(`/users/${userId}/readiness-check`, {
                headers: { Authorization: `Bearer ${state.token}` },
              });
              const failed = (readiness.checks || []).filter((c) => !c.passed);
              if (!failed.length) {
                setBoMsg(`Readiness OK for ${readiness.email || (user ? user.email : userId)}`);
              } else {
                const lines = failed.map((c) => `${c.name}: ${c.detail}`).join("\\n");
                setBoMsg(`Readiness warning for ${readiness.email || (user ? user.email : userId)}: ${failed.length} failed`, true);
                alert(`Readiness failed checks (${readiness.email || (user ? user.email : userId)}):\\n\\n${lines}`);
              }
            } catch (e) {
              setBoMsg(`Readiness check failed: ${String(e.message || e)}`, true);
            } finally {
              btn.disabled = false;
            }
          });
        });
        document.querySelectorAll(".toggle-ex-btn").forEach((btn) => {
          btn.addEventListener("click", async () => {
            const userEmail = btn.getAttribute("data-user-email");
            const exchange = btn.getAttribute("data-exchange");
            const strategyId = btn.getAttribute("data-strategy-id") || "SWING_V1";
            const nextEnabled = btn.getAttribute("data-next-enabled") === "true";
            if (!userEmail || !exchange) return;
            btn.disabled = true;
            setBoMsg(`Updating ${exchange} assignment...`);
            try {
              await api("/ops/strategy/assign", {
                method: "POST",
                headers: { Authorization: `Bearer ${state.token}`, "Content-Type": "application/json" },
                body: JSON.stringify({
                  user_email: userEmail,
                  exchange,
                  strategy_id: strategyId,
                  enabled: nextEnabled,
                }),
              });
              setBoMsg(`Assignment updated: ${userEmail} ${exchange}=${nextEnabled ? "on" : "off"}`);
              await loadAll();
            } catch (e) {
              setBoMsg(`Assignment update failed: ${String(e.message || e)}`, true);
              btn.disabled = false;
            }
          });
        });
        document.querySelectorAll(".seed-secret-btn").forEach((btn) => {
          btn.addEventListener("click", async () => {
            const userId = btn.getAttribute("data-user-id");
            const exchange = btn.getAttribute("data-exchange");
            if (!userId || !exchange) return;
            const user = state.usersById[userId];
            const apiKey = prompt(`API key for ${exchange} (${user ? user.email : userId}):`);
            if (apiKey === null) return;
            const apiSecret = prompt(`API secret for ${exchange} (${user ? user.email : userId}):`);
            if (apiSecret === null) return;
            if (!apiKey.trim() || !apiSecret) {
              setBoMsg("API key and API secret are required", true);
              return;
            }
            btn.disabled = true;
            setBoMsg(`Saving ${exchange} secret...`);
            try {
              await api(`/users/${userId}/exchange-secrets`, {
                method: "PUT",
                headers: { Authorization: `Bearer ${state.token}`, "Content-Type": "application/json" },
                body: JSON.stringify({
                  exchange,
                  api_key: apiKey.trim(),
                  api_secret: apiSecret,
                }),
              });
              setBoMsg(`Secret saved for ${user ? user.email : userId} (${exchange})`);
              await loadAll();
            } catch (e) {
              setBoMsg(`Secret save failed: ${String(e.message || e)}`, true);
              btn.disabled = false;
            }
          });
        });
        document.querySelectorAll(".del-secret-btn").forEach((btn) => {
          btn.addEventListener("click", async () => {
            const userId = btn.getAttribute("data-user-id");
            const exchange = btn.getAttribute("data-exchange");
            if (!userId || !exchange) return;
            const user = state.usersById[userId];
            const ok = confirm(`Delete ${exchange} secret for ${user ? user.email : userId}?`);
            if (!ok) return;
            btn.disabled = true;
            setBoMsg(`Deleting ${exchange} secret...`);
            try {
              await api(`/users/${userId}/exchange-secrets/${exchange}`, {
                method: "DELETE",
                headers: { Authorization: `Bearer ${state.token}` },
              });
              setBoMsg(`Secret deleted for ${user ? user.email : userId} (${exchange})`);
              await loadAll();
            } catch (e) {
              setBoMsg(`Secret delete failed: ${String(e.message || e)}`, true);
              btn.disabled = false;
            }
          });
        });
      }
    }

    async function loadAll() {
      const token = byId("token").value.trim();
      if (!token) throw new Error("Token required");
      localStorage.setItem(STORE_TOKEN, token);
      state.token = token;
      const me = await api("/users/me", { headers: { Authorization: `Bearer ${token}` } });
      state.me = me;
      byId("sessionInfo").textContent = `Signed in as ${me.email} (${me.role})`;

      if (["admin", "operator", "viewer"].includes(me.role)) {
        const reqs = [
          api("/ops/dashboard/summary?real_only=true&include_service_users=false", { headers: { Authorization: `Bearer ${token}` } }),
          api("/ops/backoffice/summary?real_only=true", { headers: { Authorization: `Bearer ${token}` } }),
          api("/ops/backoffice/users?real_only=true", { headers: { Authorization: `Bearer ${token}` } }),
        ];
        if (me.role === "admin") {
          reqs.push(api("/users", { headers: { Authorization: `Bearer ${token}` } }));
          reqs.push(api("/users/risk-profiles", { headers: { Authorization: `Bearer ${token}` } }));
          reqs.push(api("/ops/strategy/assignments", { headers: { Authorization: `Bearer ${token}` } }));
          reqs.push(api("/ops/admin/trading-control", { headers: { Authorization: `Bearer ${token}` } }));
        }
        const results = await Promise.all(reqs);
        const home = results[0];
        const boSummary = results[1];
        const boUsers = results[2];
        state.backofficeUsers = boUsers || [];
        state.usersById = {};
        state.riskProfiles = [];
        if (me.role === "admin") {
          const users = results[3] || [];
          const profiles = results[4] || [];
          const assignments = results[5] || [];
          const tradingControl = results[6] || null;
          users.forEach((u) => { state.usersById[u.id] = u; });
          state.riskProfiles = profiles;
          state.assignments = {};
          assignments.forEach((a) => {
            const k = `${(a.user_email || "").toLowerCase()}|${a.exchange}`;
            state.assignments[k] = a;
          });
          state.tradingControl = tradingControl;
          setBoMsg("Admin edit mode enabled");
          renderTradingControl(tradingControl, true);
          renderMaintenance(true);
          renderIncidentAudit(true);
          renderExecLab(true);
          renderSnapshot(true);
        } else {
          setBoMsg("Readonly mode");
          renderTradingControl(null, false);
          renderMaintenance(false);
          renderIncidentAudit(false);
          renderExecLab(state.me && ["trader", "operator"].includes(state.me.role));
          renderSnapshot(false);
        }
        fillHome(home);
        fillBackofficeSummary(boSummary);
        renderBackofficeUsersFromFilter();
      } else {
        byId("homeMsg").textContent = `Role ${me.role} has limited UI in Sprint A (backoffice is readonly for admin/operator/viewer).`;
        byId("boSummary").innerHTML = '<tr><td class="muted">No access to backoffice summary for this role</td></tr>';
        byId("boUsers").innerHTML = '<tr><td colspan="8" class="muted">No access to backoffice users for this role</td></tr>';
        setBoMsg("No backoffice access for this role", true);
        renderTradingControl(null, false);
        renderMaintenance(false);
        renderIncidentAudit(false);
        renderExecLab(state.me && ["trader", "operator"].includes(state.me.role));
        renderSnapshot(false);
      }
    }

    async function updateTradingControl(nextEnabled) {
      if (!state.token) throw new Error("Token required");
      if (!state.me || state.me.role !== "admin") throw new Error("Admin required");
      const reason = (byId("tradingCtlReason").value || "").trim();
      if (!nextEnabled && !reason) throw new Error("Reason is required to disable trading");
      const resp = await api("/ops/admin/trading-control", {
        method: "POST",
        headers: { Authorization: `Bearer ${state.token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ trading_enabled: nextEnabled, reason: reason || null }),
      });
      state.tradingControl = resp;
      renderTradingControl(resp, true);
      setTradingCtlMsg(`Trading ${nextEnabled ? "enabled" : "disabled"} successfully`);
    }

    document.querySelectorAll(".tab").forEach((b) => {
      b.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
        document.querySelectorAll(".panel").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        byId(b.dataset.tab).classList.add("active");
      });
    });

    byId("loginBtn").addEventListener("click", async () => {
      try { await login(); } catch (e) { byId("sessionInfo").textContent = String(e.message || e); setOverall("red"); }
    });
    byId("loadBtn").addEventListener("click", async () => {
      try { await loadAll(); } catch (e) { byId("sessionInfo").textContent = String(e.message || e); setOverall("red"); }
    });
    byId("refreshSessionBtn").addEventListener("click", async () => {
      try { await refreshSession(); } catch (e) { byId("sessionInfo").textContent = String(e.message || e); setOverall("red"); }
    });
    byId("logoutBtn").addEventListener("click", async () => { await logout(); });
    byId("tradingCtlDisableBtn").addEventListener("click", async () => {
      try { await updateTradingControl(false); } catch (e) { setTradingCtlMsg(String(e.message || e), true); }
    });
    byId("tradingCtlEnableBtn").addEventListener("click", async () => {
      try { await updateTradingControl(true); } catch (e) { setTradingCtlMsg(String(e.message || e), true); }
    });
    byId("tradingCtlRefreshBtn").addEventListener("click", async () => {
      try {
        const d = await api("/ops/admin/trading-control", { headers: { Authorization: `Bearer ${state.token}` } });
        state.tradingControl = d;
        renderTradingControl(d, true);
      } catch (e) {
        setTradingCtlMsg(String(e.message || e), true);
      }
    });
    byId("cleanupDryBtn").addEventListener("click", async () => {
      try {
        const older = Math.max(1, parseInt(byId("cleanupDays").value || "14", 10));
        const out = await api(`/ops/admin/cleanup-smoke-users?dry_run=true&older_than_days=${older}`, {
          method: "POST",
          headers: { Authorization: `Bearer ${state.token}` },
        });
        setMaintMsg(`Cleanup dry-run: scanned=${out.scanned} eligible=${out.eligible} deleted=${out.deleted}`);
      } catch (e) {
        setMaintMsg(String(e.message || e), true);
      }
    });
    byId("cleanupApplyBtn").addEventListener("click", async () => {
      try {
        const older = Math.max(1, parseInt(byId("cleanupDays").value || "14", 10));
        const ok = confirm(`Apply smoke cleanup now? older_than_days=${older}`);
        if (!ok) return;
        const out = await api(`/ops/admin/cleanup-smoke-users?dry_run=false&older_than_days=${older}`, {
          method: "POST",
          headers: { Authorization: `Bearer ${state.token}` },
        });
        setMaintMsg(`Cleanup applied: scanned=${out.scanned} eligible=${out.eligible} deleted=${out.deleted}`);
        await loadAll();
      } catch (e) {
        setMaintMsg(String(e.message || e), true);
      }
    });
    byId("idemStatsBtn").addEventListener("click", async () => {
      try {
        const d = await api("/ops/admin/idempotency/stats", {
          headers: { Authorization: `Bearer ${state.token}` },
        });
        setMaintMsg(`Idempotency stats: total=${d.records_total} max_age_days=${d.max_age_days}`);
      } catch (e) {
        setMaintMsg(String(e.message || e), true);
      }
    });
    byId("idemCleanupBtn").addEventListener("click", async () => {
      try {
        const ok = confirm("Run idempotency cleanup now?");
        if (!ok) return;
        const d = await api("/ops/admin/idempotency/cleanup", {
          method: "POST",
          headers: { Authorization: `Bearer ${state.token}` },
        });
        setMaintMsg(`Idempotency cleanup: deleted=${d.deleted} max_age_days=${d.max_age_days}`);
      } catch (e) {
        setMaintMsg(String(e.message || e), true);
      }
    });
    byId("openIncidentBtn").addEventListener("click", () => {
      try {
        const ts = new Date().toISOString();
        const customTitle = (byId("incidentTitle").value || "").trim();
        const title = encodeURIComponent(customTitle || `[Ops Console] Incident ${ts}`);
        const body = encodeURIComponent(
          `Opened from /ops/console\n\n- Timestamp: ${ts}\n- Context: console incident action\n`
        );
        window.open(`https://github.com/Gonzalo-Giraldo/crypto-saas/issues/new?title=${title}&body=${body}`, "_blank");
        setIncidentAuditMsg("Incident form opened in GitHub");
      } catch (e) {
        setIncidentAuditMsg(String(e.message || e), true);
      }
    });
    byId("auditLoadBtn").addEventListener("click", async () => {
      try {
        const limit = Math.min(200, Math.max(1, parseInt(byId("auditLimit").value || "20", 10)));
        const rows = await api(`/ops/audit/all?limit=${limit}`, {
          headers: { Authorization: `Bearer ${state.token}` },
        });
        byId("auditBody").innerHTML = (rows || []).map((r) => `
          <tr>
            <td class="mono">${esc(r.created_at || "")}</td>
            <td class="mono">${esc(r.user_id || "")}</td>
            <td>${esc(r.action || "")}</td>
            <td>${esc(r.entity_type || "")}</td>
          </tr>
        `).join("") || '<tr><td colspan="4" class="muted">No audit rows</td></tr>';
        setIncidentAuditMsg(`Audit loaded: ${rows.length || 0} rows`);
      } catch (e) {
        setIncidentAuditMsg(String(e.message || e), true);
      }
    });
    byId("auditExportBtn").addEventListener("click", async () => {
      try {
        const limit = Math.min(2000, Math.max(1, parseInt(byId("auditLimit").value || "20", 10) * 10));
        const out = await api(`/ops/admin/audit/export?limit=${limit}`, {
          headers: { Authorization: `Bearer ${state.token}` },
        });
        const blob = new Blob([JSON.stringify(out, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `audit_export_${new Date().toISOString().replaceAll(":", "-")}.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        setIncidentAuditMsg(`Audit export downloaded (records=${(out.meta && out.meta.records_count) || 0})`);
      } catch (e) {
        setIncidentAuditMsg(String(e.message || e), true);
      }
    });
    byId("execExchange").addEventListener("change", () => {
      const ex = byId("execExchange").value;
      byId("execSymbol").value = ex === "IBKR" ? "AAPL" : "BTCUSDT";
      byId("execQty").value = ex === "IBKR" ? "1" : "0.01";
    });
    byId("execPretradeBtn").addEventListener("click", async () => {
      try {
        const exchange = byId("execExchange").value;
        const payload = {
          symbol: (byId("execSymbol").value || "").trim(),
          side: byId("execSide").value,
          qty: Number(byId("execQty").value || "0"),
          rr_estimate: exchange === "IBKR" ? 1.4 : 1.6,
          trend_tf: "4H",
          signal_tf: "1H",
          timing_tf: "15M",
          spread_bps: 7,
          slippage_bps: 10,
          volume_24h_usdt: exchange === "IBKR" ? 0 : 90000000,
          in_rth: true,
          macro_event_block: false,
          earnings_within_24h: false,
        };
        const path = exchange === "IBKR"
          ? "/ops/execution/pretrade/ibkr/check"
          : "/ops/execution/pretrade/binance/check";
        const out = await api(path, {
          method: "POST",
          headers: { Authorization: `Bearer ${state.token}`, "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        setExecLabOut(out);
        setExecLabMsg(`Pretrade ${exchange} completed`);
      } catch (e) {
        setExecLabMsg(String(e.message || e), true);
      }
    });
    byId("execExitBtn").addEventListener("click", async () => {
      try {
        const exchange = byId("execExchange").value;
        const symbol = (byId("execSymbol").value || "").trim();
        const payload = exchange === "IBKR"
          ? {
              symbol,
              side: byId("execSide").value,
              entry_price: 180,
              current_price: 179,
              stop_loss: 178,
              take_profit: 183,
              opened_minutes: 500,
              trend_break: false,
              signal_reverse: false,
              macro_event_block: true,
              earnings_within_24h: false,
            }
          : {
              symbol,
              side: byId("execSide").value,
              entry_price: 50000,
              current_price: 50750,
              stop_loss: 49500,
              take_profit: 51000,
              opened_minutes: 180,
              trend_break: false,
              signal_reverse: false,
            };
        const path = exchange === "IBKR"
          ? "/ops/execution/exit/ibkr/check"
          : "/ops/execution/exit/binance/check";
        const out = await api(path, {
          method: "POST",
          headers: { Authorization: `Bearer ${state.token}`, "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        setExecLabOut(out);
        setExecLabMsg(`Exit check ${exchange} completed`);
      } catch (e) {
        setExecLabMsg(String(e.message || e), true);
      }
    });
    byId("execTestOrderBtn").addEventListener("click", async () => {
      try {
        const exchange = byId("execExchange").value;
        const payload = {
          symbol: (byId("execSymbol").value || "").trim(),
          side: byId("execSide").value,
          qty: Number(byId("execQty").value || "0"),
        };
        const path = exchange === "IBKR"
          ? "/ops/execution/ibkr/test-order"
          : "/ops/execution/binance/test-order";
        const out = await api(path, {
          method: "POST",
          headers: { Authorization: `Bearer ${state.token}`, "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        setExecLabOut(out);
        setExecLabMsg(`Test order ${exchange} completed`);
      } catch (e) {
        setExecLabMsg(String(e.message || e), true);
      }
    });
    byId("snapshotBuildBtn").addEventListener("click", async () => {
      try {
        const token = state.token;
        state.snapshotData = await api("/ops/admin/snapshot/daily?real_only=true&max_secret_age_days=30&recent_hours=24", {
          headers: { Authorization: `Bearer ${token}` },
        });
        setSnapshotMsg("Snapshot built successfully");
      } catch (e) {
        setSnapshotMsg(String(e.message || e), true);
      }
    });
    byId("snapshotDownloadBtn").addEventListener("click", () => {
      try {
        if (!state.snapshotData) throw new Error("Build snapshot first");
        const blob = new Blob([JSON.stringify(state.snapshotData, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `ops_snapshot_${new Date().toISOString().replaceAll(":", "-")}.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        setSnapshotMsg("Snapshot downloaded");
      } catch (e) {
        setSnapshotMsg(String(e.message || e), true);
      }
    });
    byId("boApplyFilterBtn").addEventListener("click", () => {
      try { renderBackofficeUsersFromFilter(); } catch (e) { setBoMsg(String(e.message || e), true); }
    });
    byId("boResetFilterBtn").addEventListener("click", () => {
      byId("boEmailFilter").value = "";
      byId("boRoleFilter").value = "ALL";
      try { renderBackofficeUsersFromFilter(); } catch (e) { setBoMsg(String(e.message || e), true); }
    });

    const remembered = localStorage.getItem(STORE_TOKEN) || "";
    const rememberedEmail = localStorage.getItem(STORE_EMAIL) || "";
    const rememberedRefresh = localStorage.getItem(STORE_REFRESH) || "";
    if (remembered) byId("token").value = remembered;
    if (rememberedEmail) byId("email").value = rememberedEmail;
    if (rememberedRefresh) state.refreshToken = rememberedRefresh;
  </script>
</body>
</html>
        """
    )
