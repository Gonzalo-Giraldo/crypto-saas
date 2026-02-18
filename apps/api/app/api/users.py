from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.api.app.db.session import get_db
from apps.api.app.models.user import User
from apps.api.app.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])

@router.post("", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    u = User(email=str(payload.email), display_name=payload.display_name, is_active=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    users = db.execute(select(User).order_by(User.email.asc())).scalars().all()
    return users

