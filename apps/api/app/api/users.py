from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.api.app.db.session import get_db
from apps.api.app.models.exchange_secret import ExchangeSecret
from apps.api.app.models.user_risk_profile import UserRiskProfileOverride
from apps.api.app.models.user import User
from apps.api.app.schemas.exchange_secret import ExchangeSecretOut, ExchangeSecretUpsert
from apps.api.app.schemas.user import (
    UserCreate,
    UserOut,
    UserRoleUpdate,
    UserRiskProfileUpdate,
)
from apps.api.app.api.deps import get_current_user, require_role
from apps.api.app.core.security import get_password_hash
from apps.api.app.services.audit import log_audit_event
from apps.api.app.services.exchange_secrets import upsert_exchange_secret
from apps.api.app.services.risk_profiles import list_profile_names, resolve_risk_profile
from apps.api.app.services.strategy_assignments import is_exchange_enabled_for_user

router = APIRouter(prefix="/users", tags=["users"])


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
    existing = db.execute(
        select(User).where(User.email == payload.email)
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Email already exists",
        )

    new_user = User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        role="trader",
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
        select(User).order_by(User.email.asc())
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
    normalized_role = (payload.role or "").strip().lower()
    if normalized_role not in {"admin", "trader"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="role must be admin or trader",
        )

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.role = normalized_role
    log_audit_event(
        db,
        action="user.role.updated",
        user_id=current_user.id,
        entity_type="user",
        entity_id=user.id,
        details={"target_email": user.email, "role": normalized_role},
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


@router.put("/{user_id}/risk-profile", response_model=UserOut)
def set_user_risk_profile(
    user_id: str,
    payload: UserRiskProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

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
        allowed = set(list_profile_names())
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
