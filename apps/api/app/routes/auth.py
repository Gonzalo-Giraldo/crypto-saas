from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
import pyotp

from apps.api.app.api.deps import get_current_user
from apps.api.app.db.session import get_db
from apps.api.app.models.user_2fa import UserTwoFactor
from apps.api.app.models.user import User
from apps.api.app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
)
from apps.api.app.services.audit import log_audit_event

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class Enable2FARequest(BaseModel):
    otp: str


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    otp: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.email == form_data.username)
        .first()
    )

    if not user or not verify_password(
        form_data.password,
        user.hashed_password,
        ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    user_2fa = (
        db.query(UserTwoFactor)
        .filter(UserTwoFactor.user_id == user.id)
        .first()
    )
    if user_2fa and user_2fa.enabled:
        if not otp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OTP required",
            )

        is_valid_otp = pyotp.TOTP(user_2fa.secret).verify(
            otp,
            valid_window=1,
        )
        if not is_valid_otp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid OTP",
            )

    access_token = create_access_token(
        data={
            "sub": user.email,
            "role": user.role,
        },
        expires_delta=timedelta(minutes=60),
    )

    log_audit_event(
        db,
        action="auth.login.success",
        user_id=user.id,
        entity_type="user",
        entity_id=user.id,
        details={"email": user.email},
    )
    db.commit()

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    existing_user = (
        db.query(User)
        .filter(User.email == payload.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered",
        )

    new_user = User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        role="trader",
    )

    db.add(new_user)
    db.flush()
    log_audit_event(
        db,
        action="auth.register.success",
        user_id=new_user.id,
        entity_type="user",
        entity_id=new_user.id,
        details={"email": new_user.email},
    )
    db.commit()
    db.refresh(new_user)

    return {"message": "User created successfully"}


@router.post("/2fa/setup")
def setup_2fa(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    secret = pyotp.random_base32()
    current_2fa = (
        db.query(UserTwoFactor)
        .filter(UserTwoFactor.user_id == current_user.id)
        .first()
    )

    if current_2fa:
        current_2fa.secret = secret
        current_2fa.enabled = False
    else:
        current_2fa = UserTwoFactor(
            user_id=current_user.id,
            secret=secret,
            enabled=False,
        )
        db.add(current_2fa)

    log_audit_event(
        db,
        action="auth.2fa.setup",
        user_id=current_user.id,
        entity_type="user",
        entity_id=current_user.id,
        details={"enabled": False},
    )
    db.commit()

    otpauth_uri = pyotp.TOTP(secret).provisioning_uri(
        name=current_user.email,
        issuer_name="crypto-saas",
    )

    return {
        "message": "2FA secret generated. Verify with one OTP to enable.",
        "secret": secret,
        "otpauth_uri": otpauth_uri,
    }


@router.post("/2fa/verify-enable")
def verify_enable_2fa(
    payload: Enable2FARequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_2fa = (
        db.query(UserTwoFactor)
        .filter(UserTwoFactor.user_id == current_user.id)
        .first()
    )
    if not current_2fa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="2FA setup not found. Call /auth/2fa/setup first.",
        )

    is_valid_otp = pyotp.TOTP(current_2fa.secret).verify(
        payload.otp,
        valid_window=1,
    )
    if not is_valid_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP",
        )

    current_2fa.enabled = True
    log_audit_event(
        db,
        action="auth.2fa.enabled",
        user_id=current_user.id,
        entity_type="user",
        entity_id=current_user.id,
        details={"enabled": True},
    )
    db.commit()

    return {"message": "2FA enabled"}


@router.post("/2fa/disable")
def disable_2fa(
    payload: Enable2FARequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_2fa = (
        db.query(UserTwoFactor)
        .filter(UserTwoFactor.user_id == current_user.id)
        .first()
    )
    if not current_2fa or not current_2fa.enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="2FA is not enabled",
        )

    is_valid_otp = pyotp.TOTP(current_2fa.secret).verify(
        payload.otp,
        valid_window=1,
    )
    if not is_valid_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP",
        )

    current_2fa.enabled = False
    log_audit_event(
        db,
        action="auth.2fa.disabled",
        user_id=current_user.id,
        entity_type="user",
        entity_id=current_user.id,
        details={"enabled": False},
    )
    db.commit()

    return {"message": "2FA disabled"}
