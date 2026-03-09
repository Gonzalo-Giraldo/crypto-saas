from datetime import datetime, timedelta, timezone
from typing import Optional
import threading
import time

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import func
import pyotp

from apps.api.app.api.deps import get_current_user, oauth2_scheme
from apps.api.app.db.session import get_db
from apps.api.app.models.session_revocation import SessionRevocation
from apps.api.app.models.user_2fa import UserTwoFactor
from apps.api.app.models.revoked_token import RevokedToken
from apps.api.app.models.user import User
from apps.api.app.core.security import (
    verify_password,
    get_password_hash,
    validate_password_policy,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from apps.api.app.core.config import settings
from apps.api.app.services.audit import log_audit_event

router = APIRouter(prefix="/auth", tags=["auth"])
_LOGIN_RATE_LOCK = threading.Lock()
_LOGIN_RATE_STATE: dict[tuple[str, str], list[float]] = {}


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class Enable2FARequest(BaseModel):
    otp: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


def _token_exp_to_datetime(exp_value) -> Optional[datetime]:
    try:
        return datetime.utcfromtimestamp(int(exp_value))
    except Exception:
        return None


def _to_utc_epoch_seconds(value: Optional[datetime]) -> Optional[int]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.astimezone(timezone.utc).timestamp())


def _login_rate_key(username: str, client_ip: str) -> tuple[str, str]:
    return (str(username or "").strip().lower(), str(client_ip or "").strip())


def _extract_client_ip(request: Request) -> str:
    if request is None:
        return "unknown"
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for.strip():
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    return str((request.client.host if request.client else "unknown") or "unknown")


def _check_login_rate_limit(username: str, client_ip: str) -> None:
    if not settings.AUTH_LOGIN_RATE_LIMIT_ENABLED:
        return
    window_seconds = max(60, int(settings.AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS or 300))
    max_attempts = max(1, int(settings.AUTH_LOGIN_RATE_LIMIT_MAX_ATTEMPTS or 7))
    now = time.time()
    key = _login_rate_key(username, client_ip)
    with _LOGIN_RATE_LOCK:
        attempts = [ts for ts in _LOGIN_RATE_STATE.get(key, []) if now - ts <= window_seconds]
        _LOGIN_RATE_STATE[key] = attempts
        if len(attempts) >= max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again later",
            )


def _record_login_failure(username: str, client_ip: str) -> None:
    if not settings.AUTH_LOGIN_RATE_LIMIT_ENABLED:
        return
    window_seconds = max(60, int(settings.AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS or 300))
    now = time.time()
    key = _login_rate_key(username, client_ip)
    with _LOGIN_RATE_LOCK:
        attempts = [ts for ts in _LOGIN_RATE_STATE.get(key, []) if now - ts <= window_seconds]
        attempts.append(now)
        _LOGIN_RATE_STATE[key] = attempts


def _clear_login_failures(username: str, client_ip: str) -> None:
    key = _login_rate_key(username, client_ip)
    with _LOGIN_RATE_LOCK:
        if key in _LOGIN_RATE_STATE:
            _LOGIN_RATE_STATE.pop(key, None)


def _revoke_token_payload(
    db: Session,
    payload: dict,
    user_id: str,
):
    jti = payload.get("jti")
    if not jti:
        return
    exists = (
        db.query(RevokedToken)
        .filter(RevokedToken.jti == jti)
        .first()
    )
    if exists:
        return
    db.add(
        RevokedToken(
            jti=jti,
            user_id=user_id,
            token_type=str(payload.get("typ") or "unknown"),
            expires_at=_token_exp_to_datetime(payload.get("exp")),
        )
    )


def _enforced_2fa_emails() -> set[str]:
    raw = settings.ENFORCE_2FA_EMAILS or ""
    return {
        e.strip().lower()
        for e in raw.split(",")
        if e.strip()
    }


def _totp_valid_window() -> int:
    """
    OTP tolerance in 30-second steps.
    Clamp to a safe range to avoid accidental overexposure.
    """
    try:
        configured = int(settings.AUTH_TOTP_VALID_WINDOW)
    except Exception:
        configured = 1
    return max(0, min(configured, 3))


def _normalize_otp(value: Optional[str]) -> str:
    # Accept user input with spaces or separators; keep digits only.
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _is_2fa_login_temporarily_disabled() -> bool:
    """
    Temporary bypass switch for login OTP checks.
    - Fail-closed on malformed date values.
    - If disabled with no end date, bypass remains active (not recommended).
    """
    if settings.AUTH_2FA_LOGIN_ENABLED:
        return False
    raw_until = str(settings.AUTH_2FA_TEMP_DISABLE_UNTIL_UTC or "").strip()
    if not raw_until:
        return True
    try:
        normalized = raw_until.replace("Z", "+00:00")
        until_dt = datetime.fromisoformat(normalized)
    except Exception:
        return False
    if until_dt.tzinfo is None:
        until_dt = until_dt.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) <= until_dt.astimezone(timezone.utc)


def _is_password_expired(user: User) -> bool:
    if not settings.ENFORCE_PASSWORD_MAX_AGE:
        return False
    max_age_days = int(settings.PASSWORD_MAX_AGE_DAYS or 0)
    if max_age_days <= 0:
        return False
    changed_at = user.password_changed_at
    if changed_at is None:
        return True
    if changed_at.tzinfo is None:
        changed_at = changed_at.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - changed_at.astimezone(timezone.utc)).days
    return age_days > max_age_days


def _issued_at_after_revocation(
    db: Session,
    user_id: str,
) -> datetime:
    now_ts = int(datetime.now(timezone.utc).timestamp())
    row = (
        db.query(SessionRevocation)
        .filter(SessionRevocation.user_id == user_id)
        .first()
    )
    if not row:
        return datetime.utcfromtimestamp(now_ts)
    marker_ts = _to_utc_epoch_seconds(row.revoked_after)
    if marker_ts is None:
        return datetime.utcfromtimestamp(now_ts)
    target_ts = max(now_ts, marker_ts + 1)
    return datetime.utcfromtimestamp(target_ts)


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    otp: Optional[str] = Form(default=None),
    request: Request = None,
    db: Session = Depends(get_db),
):
    username_norm = str(form_data.username or "").strip().lower()
    client_ip = _extract_client_ip(request)
    _check_login_rate_limit(username_norm, client_ip)
    user = (
        db.query(User)
        .filter(func.lower(User.email) == username_norm)
        .first()
    )

    if not user or not verify_password(
        form_data.password,
        user.hashed_password,
        ):
        _record_login_failure(username_norm, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if user.role == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is disabled",
        )
    if _is_password_expired(user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password expired. Contact admin to reset credentials",
        )

    user_2fa = (
        db.query(UserTwoFactor)
        .filter(UserTwoFactor.user_id == user.id)
        .first()
    )
    enforce_2fa = (
        user.email.lower() in _enforced_2fa_emails()
        or (settings.ENFORCE_2FA_FOR_ADMINS and user.role == "admin")
    )

    if enforce_2fa and (not user_2fa or not user_2fa.enabled):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="2FA must be enabled for this account",
        )

    skip_login_2fa = _is_2fa_login_temporarily_disabled()
    if user_2fa and user_2fa.enabled and not skip_login_2fa:
        otp_normalized = _normalize_otp(otp)
        if not otp_normalized:
            _record_login_failure(username_norm, client_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OTP required",
            )

        is_valid_otp = pyotp.TOTP(user_2fa.secret).verify(
            otp_normalized,
            valid_window=_totp_valid_window(),
        )
        if not is_valid_otp:
            _record_login_failure(username_norm, client_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid OTP",
            )

    _clear_login_failures(username_norm, client_ip)
    issued_at = _issued_at_after_revocation(db, user.id)
    access_token = create_access_token(
        data={
            "sub": user.email,
            "role": user.role,
            "uid": user.id,
            "tid": user.tenant_id,
        },
        expires_delta=timedelta(minutes=60),
        issued_at=issued_at,
    )
    refresh_token = create_refresh_token(
        data={
            "sub": user.email,
            "role": user.role,
            "uid": user.id,
            "tid": user.tenant_id,
        },
        expires_delta=timedelta(days=7),
        issued_at=issued_at,
    )

    log_audit_event(
        db,
        action="auth.login.success",
        user_id=user.id,
        entity_type="user",
        entity_id=user.id,
        details={
            "email": user.email,
            "login_2fa_bypassed": bool(skip_login_2fa),
        },
    )
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh")
def refresh_tokens(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
):
    token_payload = decode_token(payload.refresh_token)
    if not token_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    if token_payload.get("typ") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    jti = token_payload.get("jti")
    if jti:
        revoked = (
            db.query(RevokedToken)
            .filter(RevokedToken.jti == jti)
            .first()
        )
        if revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token revoked",
            )

    user_email = token_payload.get("sub")
    user = (
        db.query(User)
        .filter(User.email == user_email)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if user.role == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is disabled",
        )
    if _is_password_expired(user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password expired. Contact admin to reset credentials",
        )
    session_revoke = (
        db.query(SessionRevocation)
        .filter(SessionRevocation.user_id == user.id)
        .first()
    )
    token_iat = token_payload.get("iat")
    if session_revoke and token_iat:
        try:
            iat_ts = int(token_iat)
            revoke_cutoff_ts = _to_utc_epoch_seconds(session_revoke.revoked_after)
        except Exception:
            iat_ts = None
            revoke_cutoff_ts = None
        if iat_ts is not None and revoke_cutoff_ts is not None and iat_ts <= revoke_cutoff_ts:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session revoked",
            )

    _revoke_token_payload(db, token_payload, user.id)
    issued_at = _issued_at_after_revocation(db, user.id)
    new_access = create_access_token(
        data={
            "sub": user.email,
            "role": user.role,
            "uid": user.id,
            "tid": user.tenant_id,
        },
        expires_delta=timedelta(minutes=60),
        issued_at=issued_at,
    )
    new_refresh = create_refresh_token(
        data={
            "sub": user.email,
            "role": user.role,
            "uid": user.id,
            "tid": user.tenant_id,
        },
        expires_delta=timedelta(days=7),
        issued_at=issued_at,
    )
    log_audit_event(
        db,
        action="auth.refresh.success",
        user_id=user.id,
        entity_type="user",
        entity_id=user.id,
        details={"email": user.email},
    )
    db.commit()

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(
    payload: LogoutRequest,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    access_payload = decode_token(token)
    if access_payload:
        _revoke_token_payload(db, access_payload, current_user.id)

    if payload.refresh_token:
        refresh_payload = decode_token(payload.refresh_token)
        if refresh_payload and refresh_payload.get("sub") == current_user.email:
            _revoke_token_payload(db, refresh_payload, current_user.id)

    log_audit_event(
        db,
        action="auth.logout.success",
        user_id=current_user.id,
        entity_type="user",
        entity_id=current_user.id,
        details={"email": current_user.email},
    )
    db.commit()
    return {"message": "Session revoked"}


@router.post("/revoke-all")
def revoke_all_sessions(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    access_payload = decode_token(token)
    if access_payload:
        _revoke_token_payload(db, access_payload, current_user.id)

    row = (
        db.query(SessionRevocation)
        .filter(SessionRevocation.user_id == current_user.id)
        .first()
    )
    now = datetime.utcnow()
    if row:
        row.revoked_after = now
    else:
        db.add(
            SessionRevocation(
                user_id=current_user.id,
                revoked_after=now,
            )
        )

    log_audit_event(
        db,
        action="auth.revoke_all.requested",
        user_id=current_user.id,
        entity_type="user",
        entity_id=current_user.id,
        details={"email": current_user.email},
    )
    db.commit()
    return {"message": "All previous sessions revoked"}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    if not settings.AUTH_PUBLIC_REGISTER_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled",
        )

    password_error = validate_password_policy(payload.password)
    if password_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=password_error,
        )

    existing_user = (
        db.query(User)
        .filter(func.lower(User.email) == str(payload.email).lower())
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered",
        )

    new_user = User(
        email=payload.email,
        tenant_id="default",
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
