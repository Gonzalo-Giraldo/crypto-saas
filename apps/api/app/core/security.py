from datetime import datetime, timedelta
import uuid
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


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
):
    return create_token(
        data=data,
        token_type="access",
        expires_delta=expires_delta or timedelta(minutes=60),
    )


def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
):
    return create_token(
        data=data,
        token_type="refresh",
        expires_delta=expires_delta or timedelta(days=7),
    )


def create_token(
    data: dict,
    token_type: str,
    expires_delta: timedelta,
):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update(
        {
            "exp": expire,
            "iat": datetime.utcnow(),
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
