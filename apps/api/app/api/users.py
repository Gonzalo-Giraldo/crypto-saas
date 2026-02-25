from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.api.app.db.session import get_db
from apps.api.app.models.user import User
from apps.api.app.schemas.user import UserCreate, UserOut
from apps.api.app.api.deps import get_current_user, require_role
from apps.api.app.core.security import get_password_hash

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
