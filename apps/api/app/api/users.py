from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.api.app.db.session import get_db
from apps.api.app.models.exchange_secret import ExchangeSecret
from apps.api.app.models.user import User
from apps.api.app.schemas.exchange_secret import ExchangeSecretOut, ExchangeSecretUpsert
from apps.api.app.schemas.user import UserCreate, UserOut
from apps.api.app.api.deps import get_current_user, require_role
from apps.api.app.core.security import get_password_hash
from apps.api.app.services.audit import log_audit_event
from apps.api.app.services.exchange_secrets import upsert_exchange_secret

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

    return new_user


# 🔹 Listar usuarios (solo admin)
@router.get(
    "",
    response_model=list[UserOut],
)
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    users = db.execute(
        select(User).order_by(User.email.asc())
    ).scalars().all()

    return users


# 🔹 Usuario autenticado actual
@router.get("/me", response_model=UserOut)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.post("/exchange-secrets", status_code=status.HTTP_201_CREATED)
def save_exchange_secret(
    payload: ExchangeSecretUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
