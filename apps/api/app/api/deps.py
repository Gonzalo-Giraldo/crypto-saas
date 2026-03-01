from datetime import datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from apps.api.app.db.session import get_db
from apps.api.app.models.session_revocation import SessionRevocation
from apps.api.app.models.revoked_token import RevokedToken
from apps.api.app.models.user import User
from apps.api.app.core.security import decode_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Validates JWT token and returns the authenticated user.
    """

    payload = decode_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    user_email = payload.get("sub")
    token_type = payload.get("typ")
    token_jti = payload.get("jti")
    token_iat = payload.get("iat")

    if user_email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    if token_jti:
        revoked = (
            db.query(RevokedToken)
            .filter(RevokedToken.jti == token_jti)
            .first()
        )
        if revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked",
            )

    user = (
        db.query(User)
        .filter(User.email == user_email)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if user.role == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is disabled",
        )

    session_revoke = (
        db.query(SessionRevocation)
        .filter(SessionRevocation.user_id == user.id)
        .first()
    )
    if session_revoke and token_iat:
        try:
            iat_dt = datetime.utcfromtimestamp(int(token_iat))
        except Exception:
            iat_dt = None
        if iat_dt and iat_dt <= session_revoke.revoked_after.replace(tzinfo=None):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session revoked",
            )

    return user


def require_role(required_role: str):
    """
    Dependency factory to require a specific role.
    Usage:
        current_user: User = Depends(require_role("admin"))
    """

    def role_checker(
        current_user: User = Depends(get_current_user),
    ):
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        return current_user

    return role_checker
