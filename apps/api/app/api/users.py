from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, select
import pyotp

from apps.api.app.db.session import get_db
from apps.api.app.models.exchange_secret import ExchangeSecret
from apps.api.app.models.user_2fa import UserTwoFactor
from apps.api.app.models.user_risk_profile import UserRiskProfileOverride
from apps.api.app.models.user_risk_settings import UserRiskSettings
from apps.api.app.models.user import User
from apps.api.app.schemas.exchange_secret import ExchangeSecretOut, ExchangeSecretUpsert
from apps.api.app.schemas.user import (
    UserCreate,
    UserOut,
    UserRoleUpdate,
    UserRiskProfileUpdate,
    UserEmailUpdate,
    UserPasswordUpdate,
    User2FAResetOut,
    UserRiskSettingsOut,
    UserRiskSettingsUpdate,
)
from apps.api.app.core.config import settings
from apps.api.app.api.deps import get_current_user, require_role
from apps.api.app.core.security import get_password_hash, validate_password_policy
from apps.api.app.services.audit import log_audit_event
from apps.api.app.services.exchange_secrets import upsert_exchange_secret
from apps.api.app.services.risk_profiles import list_profile_names, resolve_risk_profile
from apps.api.app.services.strategy_assignments import is_exchange_enabled_for_user
from apps.api.app.services.user_readiness import (
    build_readiness_report,
    build_user_readiness,
    is_real_user_email,
    is_service_user_email,
)

router = APIRouter(prefix="/users", tags=["users"])
ALLOWED_USER_ROLES = {"admin", "operator", "viewer", "trader", "disabled"}


def _tenant_id(user: User) -> str:
    return (user.tenant_id or "default")


def _validate_change_reason(reason: str | None) -> str:
    normalized = (reason or "").strip()
    if len(normalized) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="reason must contain at least 8 characters",
        )
    return normalized


def _tenant_user_or_404(db: Session, user_id: str, current_user: User) -> User:
    user = db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == _tenant_id(current_user),
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _build_user_readiness(db: Session, user: User) -> dict:
    return build_user_readiness(db, user)


# 🔹 Crear usuario (solo admin)
@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    password_error = validate_password_policy(payload.password)
    if password_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=password_error,
        )

    email_norm = str(payload.email).strip().lower()
    existing = db.execute(
        select(User).where(func.lower(User.email) == email_norm)
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Email already exists",
        )

    new_user = User(
        email=email_norm,
        tenant_id=_tenant_id(current_user),
        hashed_password=get_password_hash(payload.password),
        role="trader",
        password_changed_at=datetime.now(timezone.utc),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    profile = resolve_risk_profile(db, new_user.id, new_user.email)
    return UserOut(
        id=new_user.id,
        email=new_user.email,
        role=new_user.role,
        risk_profile=profile["profile_name"],
        risk_profile_source="default",
    )


# 🔹 Listar usuarios (solo admin)
@router.get(
    "",
    response_model=list[UserOut],
)
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    user_rows = db.execute(
        select(User)
        .where(User.tenant_id == _tenant_id(current_user))
        .order_by(User.email.asc())
    ).scalars().all()

    overrides = db.execute(
        select(UserRiskProfileOverride)
    ).scalars().all()
    override_map = {r.user_id: r.profile_name for r in overrides}

    out = []
    for u in user_rows:
        profile = resolve_risk_profile(db, u.id, u.email)
        out.append(
            UserOut(
                id=u.id,
                email=u.email,
                role=u.role,
                risk_profile=profile["profile_name"],
                risk_profile_source="override" if u.id in override_map else "default",
            )
        )
    return out


@router.patch("/{user_id}/role", response_model=UserOut)
def update_user_role(
    user_id: str,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    change_reason = _validate_change_reason(payload.reason)
    normalized_role = (payload.role or "").strip().lower()
    if normalized_role not in ALLOWED_USER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="role must be one of: admin, operator, viewer, trader, disabled",
        )

    user = _tenant_user_or_404(db, user_id, current_user)
    if user.id == current_user.id and normalized_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove your own admin role",
        )
    if user.role == "admin" and normalized_role != "admin":
        admin_count = db.execute(
            select(func.count()).select_from(User).where(
                User.role == "admin",
                User.tenant_id == _tenant_id(current_user),
            )
        ).scalar_one()
        if int(admin_count) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote/disable the last admin",
            )

    user.role = normalized_role
    log_audit_event(
        db,
        action="user.role.updated",
        user_id=current_user.id,
        entity_type="user",
        entity_id=user.id,
        details={"target_email": user.email, "role": normalized_role, "reason": change_reason},
    )
    db.commit()
    db.refresh(user)

    profile = resolve_risk_profile(db, user.id, user.email)
    override = db.execute(
        select(UserRiskProfileOverride).where(UserRiskProfileOverride.user_id == user.id)
    ).scalar_one_or_none()
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        risk_profile=profile["profile_name"],
        risk_profile_source="override" if override else "default",
    )


@router.patch("/{user_id}/email", response_model=UserOut)
def update_user_email(
    user_id: str,
    payload: UserEmailUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    change_reason = _validate_change_reason(payload.reason)
    user = _tenant_user_or_404(db, user_id, current_user)

    new_email = payload.email.strip().lower()
    existing = db.execute(
        select(User).where(func.lower(User.email) == new_email, User.id != user_id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    old_email = user.email
    user.email = new_email
    log_audit_event(
        db,
        action="user.email.updated",
        user_id=current_user.id,
        entity_type="user",
        entity_id=user.id,
        details={"old_email": old_email, "new_email": new_email, "reason": change_reason},
    )
    db.commit()
    db.refresh(user)

    profile = resolve_risk_profile(db, user.id, user.email)
    override = db.execute(
        select(UserRiskProfileOverride).where(UserRiskProfileOverride.user_id == user.id)
    ).scalar_one_or_none()
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        risk_profile=profile["profile_name"],
        risk_profile_source="override" if override else "default",
    )


@router.put("/{user_id}/password")
def update_user_password(
    user_id: str,
    payload: UserPasswordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    change_reason = _validate_change_reason(payload.reason)
    user = _tenant_user_or_404(db, user_id, current_user)

    new_password = (payload.new_password or "").strip()
    password_error = validate_password_policy(new_password)
    if password_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=password_error,
        )

    user.hashed_password = get_password_hash(new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    log_audit_event(
        db,
        action="user.password.updated",
        user_id=current_user.id,
        entity_type="user",
        entity_id=user.id,
        details={"target_email": user.email, "reason": change_reason},
    )
    db.commit()
    return {"message": "Password updated"}


@router.post("/{user_id}/2fa/reset", response_model=User2FAResetOut)
def reset_user_2fa(
    user_id: str,
    reason: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    change_reason = _validate_change_reason(reason)
    user = _tenant_user_or_404(db, user_id, current_user)
    secret = pyotp.random_base32()
    issuer = getattr(settings, "APP_2FA_ISSUER", None) or "crypto-saas"
    otpauth_uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.email,
        issuer_name=issuer,
    )

    row = db.execute(
        select(UserTwoFactor).where(UserTwoFactor.user_id == user.id)
    ).scalar_one_or_none()
    if row:
        row.secret = secret
        row.enabled = True
    else:
        db.add(UserTwoFactor(user_id=user.id, secret=secret, enabled=True))

    log_audit_event(
        db,
        action="user.2fa.reset",
        user_id=current_user.id,
        entity_type="user",
        entity_id=user.id,
        details={"target_email": user.email, "reason": change_reason},
    )
    db.commit()
    return User2FAResetOut(
        user_id=user.id,
        email=user.email,
        enabled=True,
        secret=secret,
        otpauth_uri=otpauth_uri,
        message="2FA reset and enabled with new secret",
    )


@router.put("/{user_id}/risk-profile", response_model=UserOut)
def set_user_risk_profile(
    user_id: str,
    payload: UserRiskProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    user = _tenant_user_or_404(db, user_id, current_user)

    row = db.execute(
        select(UserRiskProfileOverride).where(UserRiskProfileOverride.user_id == user.id)
    ).scalar_one_or_none()

    profile_name = (payload.profile_name or "").strip()
    if profile_name == "":
        if row:
            db.delete(row)
            action = "user.risk_profile.override.cleared"
        else:
            action = "user.risk_profile.override.noop"
    else:
        allowed = set(list_profile_names(db))
        if profile_name not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"profile_name must be one of: {sorted(allowed)}",
            )
        if row:
            row.profile_name = profile_name
        else:
            row = UserRiskProfileOverride(user_id=user.id, profile_name=profile_name)
            db.add(row)
        action = "user.risk_profile.override.set"

    log_audit_event(
        db,
        action=action,
        user_id=current_user.id,
        entity_type="user",
        entity_id=user.id,
        details={"target_email": user.email, "profile_name": profile_name or None},
    )
    db.commit()
    db.refresh(user)

    profile = resolve_risk_profile(db, user.id, user.email)
    override = db.execute(
        select(UserRiskProfileOverride).where(UserRiskProfileOverride.user_id == user.id)
    ).scalar_one_or_none()
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        risk_profile=profile["profile_name"],
        risk_profile_source="override" if override else "default",
    )


@router.get("/risk-profiles", response_model=list[str])
def get_risk_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    return list_profile_names(db)


@router.get("/{user_id}/readiness-check")
def get_user_readiness_check(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    user = _tenant_user_or_404(db, user_id, current_user)
    return _build_user_readiness(db, user)


@router.get("/{user_id}/risk-settings", response_model=UserRiskSettingsOut)
def get_user_risk_settings(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    user = _tenant_user_or_404(db, user_id, current_user)
    row = db.execute(
        select(UserRiskSettings).where(UserRiskSettings.user_id == user.id)
    ).scalar_one_or_none()
    capital = float(row.capital_base_usd) if row else float(settings.DEFAULT_CAPITAL_BASE_USD)
    updated_at = row.updated_at.isoformat() if row and row.updated_at else None
    return UserRiskSettingsOut(
        user_id=user.id,
        capital_base_usd=capital,
        updated_at=updated_at,
    )


@router.put("/{user_id}/risk-settings", response_model=UserRiskSettingsOut)
def put_user_risk_settings(
    user_id: str,
    payload: UserRiskSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    user = _tenant_user_or_404(db, user_id, current_user)
    capital = float(payload.capital_base_usd)
    if capital <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="capital_base_usd must be > 0")

    row = db.execute(
        select(UserRiskSettings).where(UserRiskSettings.user_id == user.id)
    ).scalar_one_or_none()
    if not row:
        row = UserRiskSettings(user_id=user.id, capital_base_usd=capital)
        db.add(row)
    else:
        row.capital_base_usd = capital

    log_audit_event(
        db,
        action="user.risk_settings.updated",
        user_id=current_user.id,
        entity_type="risk",
        entity_id=user.id,
        details={"target_email": user.email, "capital_base_usd": capital},
    )
    db.commit()
    db.refresh(row)
    return UserRiskSettingsOut(
        user_id=user.id,
        capital_base_usd=float(row.capital_base_usd),
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


@router.get("/readiness/report")
def get_readiness_report(
    real_only: bool = True,
    include_service_users: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    users = db.execute(
        select(User)
        .where(User.tenant_id == _tenant_id(current_user))
        .order_by(User.email.asc())
    ).scalars().all()
    report = build_readiness_report(
        db,
        users=users,
        real_only=real_only,
        include_service_users=include_service_users,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_for": current_user.email,
        "real_only": real_only,
        "include_service_users": include_service_users,
        "summary": report["summary"],
        "users": report["users"],
    }


# 🔹 Usuario autenticado actual
@router.get("/me", response_model=UserOut)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = resolve_risk_profile(db, current_user.id, current_user.email)
    override = db.execute(
        select(UserRiskProfileOverride).where(UserRiskProfileOverride.user_id == current_user.id)
    ).scalar_one_or_none()
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        risk_profile=profile["profile_name"],
        risk_profile_source="override" if override else "default",
    )


@router.post("/exchange-secrets", status_code=status.HTTP_201_CREATED)
def save_exchange_secret(
    payload: ExchangeSecretUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not is_exchange_enabled_for_user(
        db=db,
        user_id=current_user.id,
        exchange=payload.exchange,
    ):
        log_audit_event(
            db,
            action="exchange.secret.upsert.blocked",
            user_id=current_user.id,
            entity_type="exchange_secret",
            details={"exchange": payload.exchange},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Exchange {payload.exchange} is disabled for this user",
        )

    row = upsert_exchange_secret(
        db=db,
        user_id=current_user.id,
        exchange=payload.exchange,
        api_key=payload.api_key,
        api_secret=payload.api_secret,
    )
    db.flush()
    log_audit_event(
        db,
        action="exchange.secret.upsert",
        user_id=current_user.id,
        entity_type="exchange_secret",
        entity_id=row.id,
        details={"exchange": row.exchange},
    )
    db.commit()
    return {"message": f"Encrypted credentials saved for {row.exchange}"}


@router.put("/{user_id}/exchange-secrets", status_code=status.HTTP_201_CREATED)
def save_exchange_secret_for_user(
    user_id: str,
    payload: ExchangeSecretUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    user = _tenant_user_or_404(db, user_id, current_user)

    row = upsert_exchange_secret(
        db=db,
        user_id=user.id,
        exchange=payload.exchange,
        api_key=payload.api_key,
        api_secret=payload.api_secret,
    )
    db.flush()
    log_audit_event(
        db,
        action="exchange.secret.upsert.admin",
        user_id=current_user.id,
        entity_type="exchange_secret",
        entity_id=row.id,
        details={"exchange": row.exchange, "target_email": user.email},
    )
    db.commit()
    return {"message": f"Encrypted credentials saved for {row.exchange} ({user.email})"}


@router.get("/{user_id}/exchange-secrets", response_model=list[ExchangeSecretOut])
def list_exchange_secrets_for_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    user = _tenant_user_or_404(db, user_id, current_user)

    rows = (
        db.execute(
            select(ExchangeSecret)
            .where(ExchangeSecret.user_id == user.id)
            .order_by(ExchangeSecret.exchange.asc())
        )
        .scalars()
        .all()
    )
    return [
        ExchangeSecretOut(
            exchange=row.exchange,
            configured=True,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.get("/exchange-secrets", response_model=list[ExchangeSecretOut])
def list_exchange_secrets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.execute(
            select(ExchangeSecret)
            .where(ExchangeSecret.user_id == current_user.id)
            .order_by(ExchangeSecret.exchange.asc())
        )
        .scalars()
        .all()
    )

    return [
        ExchangeSecretOut(
            exchange=row.exchange,
            configured=True,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.delete("/exchange-secrets/{exchange}")
def delete_exchange_secret(
    exchange: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    normalized_exchange = exchange.upper()
    if normalized_exchange not in {"BINANCE", "IBKR"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="exchange must be BINANCE or IBKR",
        )

    row = (
        db.execute(
            select(ExchangeSecret).where(
                ExchangeSecret.user_id == current_user.id,
                ExchangeSecret.exchange == normalized_exchange,
            )
        )
        .scalar_one_or_none()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No credentials found for this exchange",
        )

    entity_id = row.id
    db.delete(row)
    log_audit_event(
        db,
        action="exchange.secret.delete",
        user_id=current_user.id,
        entity_type="exchange_secret",
        entity_id=entity_id,
        details={"exchange": normalized_exchange},
    )
    db.commit()

    return {"message": f"Credentials deleted for {normalized_exchange}"}


@router.delete("/{user_id}/exchange-secrets/{exchange}")
def delete_exchange_secret_for_user(
    user_id: str,
    exchange: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    user = _tenant_user_or_404(db, user_id, current_user)

    normalized_exchange = exchange.upper()
    if normalized_exchange not in {"BINANCE", "IBKR"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="exchange must be BINANCE or IBKR",
        )

    row = (
        db.execute(
            select(ExchangeSecret).where(
                ExchangeSecret.user_id == user.id,
                ExchangeSecret.exchange == normalized_exchange,
            )
        )
        .scalar_one_or_none()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No credentials found for this exchange",
        )

    entity_id = row.id
    db.delete(row)
    log_audit_event(
        db,
        action="exchange.secret.delete.admin",
        user_id=current_user.id,
        entity_type="exchange_secret",
        entity_id=entity_id,
        details={"exchange": normalized_exchange, "target_email": user.email},
    )
    db.commit()
    return {"message": f"Credentials deleted for {normalized_exchange} ({user.email})"}
