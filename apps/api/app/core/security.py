from datetime import datetime, timedelta
import uuid
import re
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from apps.api.app.core.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password_policy(password: str) -> Optional[str]:
    pwd = str(password or "")
    min_len = max(8, int(settings.AUTH_PASSWORD_MIN_LENGTH or 10))
    if len(pwd) < min_len:
        return f"Password must be at least {min_len} characters long"
    if settings.AUTH_PASSWORD_REQUIRE_UPPER and re.search(r"[A-Z]", pwd) is None:
        return "Password must include at least one uppercase letter"
    if settings.AUTH_PASSWORD_REQUIRE_LOWER and re.search(r"[a-z]", pwd) is None:
        return "Password must include at least one lowercase letter"
    if settings.AUTH_PASSWORD_REQUIRE_DIGIT and re.search(r"[0-9]", pwd) is None:
        return "Password must include at least one digit"
    if settings.AUTH_PASSWORD_REQUIRE_SPECIAL and re.search(r"[^A-Za-z0-9]", pwd) is None:
        return "Password must include at least one special character"
    return None


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    issued_at: Optional[datetime] = None,
):
    return create_token(
        data=data,
        token_type="access",
        expires_delta=expires_delta or timedelta(minutes=60),
        issued_at=issued_at,
    )


def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    issued_at: Optional[datetime] = None,
):
    return create_token(
        data=data,
        token_type="refresh",
        expires_delta=expires_delta or timedelta(days=7),
        issued_at=issued_at,
    )


def create_token(
    data: dict,
    token_type: str,
    expires_delta: timedelta,
    issued_at: Optional[datetime] = None,
):
    to_encode = data.copy()
    iat = issued_at or datetime.utcnow()
    expire = iat + expires_delta
    to_encode.update(
        {
            "exp": expire,
            "iat": iat,
            "typ": token_type,
            "jti": str(uuid.uuid4()),
        }
    )

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )

    return encoded_jwt


def decode_token(token: str):
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        return payload
    except JWTError:
        return None
