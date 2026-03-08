from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.models.exchange_secret import ExchangeSecret
from apps.api.app.models.strategy_assignment import StrategyAssignment
from apps.api.app.models.user import User
from apps.api.app.models.user_2fa import UserTwoFactor

ALLOWED_USER_ROLES = {"admin", "operator", "viewer", "trader", "disabled"}


def is_real_user_email(email: str) -> bool:
    e = (email or "").lower()
    if e.startswith("smoke.") or e.startswith("disabled_"):
        return False
    if e.endswith("@example.com") or e.endswith("@example.invalid"):
        return False
    return True


def is_service_user_email(email: str) -> bool:
    return (email or "").lower().startswith("ops.bot.")


def build_user_readiness(db: Session, user: User) -> dict:
    user_2fa = (
        db.execute(select(UserTwoFactor).where(UserTwoFactor.user_id == user.id))
        .scalar_one_or_none()
    )
    two_factor_enabled = bool(user_2fa and user_2fa.enabled)

    secret_rows = db.execute(
        select(ExchangeSecret.exchange).where(ExchangeSecret.user_id == user.id)
    ).all()
    secret_set = {row[0] for row in secret_rows}

    assignment_rows = db.execute(
        select(StrategyAssignment.exchange, StrategyAssignment.enabled).where(
            StrategyAssignment.user_id == user.id
        )
    ).all()
    assignment_enabled = {
        exchange: bool(enabled)
        for exchange, enabled in assignment_rows
    }

    changed_at = user.password_changed_at
    if changed_at is not None and changed_at.tzinfo is None:
        changed_at = changed_at.replace(tzinfo=timezone.utc)
    max_age_days = int(settings.PASSWORD_MAX_AGE_DAYS or 0)
    enforce_max_age = bool(settings.ENFORCE_PASSWORD_MAX_AGE and max_age_days > 0)
    if changed_at is None:
        password_age_days = None
    else:
        password_age_days = max(0, (datetime.now(timezone.utc) - changed_at.astimezone(timezone.utc)).days)

    checks: list[dict] = []
    checks.append(
        {
            "name": "role_allowed",
            "passed": user.role in ALLOWED_USER_ROLES,
            "detail": user.role,
        }
    )
    checks.append(
        {
            "name": "password_not_expired",
            "passed": (not enforce_max_age) or (password_age_days is not None and password_age_days <= max_age_days),
            "detail": f"age_days={password_age_days} max_age_days={max_age_days} enforced={enforce_max_age}",
        }
    )
    checks.append(
        {
            "name": "admin_has_2fa",
            "passed": (user.role != "admin") or two_factor_enabled,
            "detail": f"two_factor_enabled={two_factor_enabled}",
        }
    )
    for exchange in ("BINANCE", "IBKR"):
        enabled_for_user = assignment_enabled.get(exchange, False)
        has_secret = exchange in secret_set
        checks.append(
            {
                "name": f"{exchange.lower()}_enabled_has_secret",
                "passed": (not enabled_for_user) or has_secret,
                "detail": f"enabled={enabled_for_user} secret_configured={has_secret}",
            }
        )

    return {
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
        "password_age_days": password_age_days,
        "password_max_age_days": max_age_days if enforce_max_age else None,
        "two_factor_enabled": two_factor_enabled,
        "assignments": assignment_enabled,
        "secrets_configured": sorted(secret_set),
        "checks": checks,
        "ready": all(bool(c["passed"]) for c in checks),
    }


def build_readiness_report(
    db: Session,
    *,
    users: list[User],
    real_only: bool,
    include_service_users: bool,
) -> dict:
    rows = []
    ready = 0
    missing = 0
    for user in users:
        if real_only and not is_real_user_email(user.email):
            continue
        if not include_service_users and is_service_user_email(user.email):
            continue
        item = build_user_readiness(db, user)
        if item["ready"]:
            ready += 1
        else:
            missing += 1
        rows.append(item)

    return {
        "summary": {
            "total_users": len(rows),
            "ready_users": ready,
            "missing_users": missing,
        },
        "users": rows,
    }
