import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from models import RevokedToken


def create_access_token(
    user_id: int,
    role: str = "user",
    extra_claims: Optional[dict[str, Any]] = None,
) -> tuple[str, str, int]:
    """
    Generate a new JWT access token.
    Returns: (token_str, jti, expires_in_seconds)
    """
    jti = str(uuid.uuid4())
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire_time = datetime.now(timezone.utc) + expires_delta

    to_encode: dict[str, Any] = {
        "sub": str(user_id),
        "user_id": user_id,
        "role": role,
        "type": "access",
        "jti": jti,
        "exp": expire_time,
        "iat": datetime.now(timezone.utc),
    }
    if extra_claims:
        to_encode.update(extra_claims)

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    expires_in_seconds = int(expires_delta.total_seconds())
    return encoded_jwt, jti, expires_in_seconds


def create_refresh_token(
    user_id: int,
    extra_claims: Optional[dict[str, Any]] = None,
) -> tuple[str, str, int]:
    """
    Generate a new JWT refresh token.
    Returns: (token_str, jti, expires_in_seconds)
    """
    jti = str(uuid.uuid4())
    expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    expire_time = datetime.now(timezone.utc) + expires_delta

    to_encode: dict[str, Any] = {
        "sub": str(user_id),
        "user_id": user_id,
        "type": "refresh",
        "jti": jti,
        "exp": expire_time,
        "iat": datetime.now(timezone.utc),
    }
    if extra_claims:
        to_encode.update(extra_claims)

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    expires_in_seconds = int(expires_delta.total_seconds())
    return encoded_jwt, jti, expires_in_seconds


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """
    Decode and validate a JWT token string.
    Returns payload dict or None if invalid/expired.
    """
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None


def is_token_revoked(db: Session, jti: str) -> bool:
    """Check if token's jti has been blacklisted/revoked."""
    revoked = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
    return revoked is not None


def revoke_token(
    db: Session,
    jti: str,
    token_type: str,
    user_id: int,
    expires_at: Optional[datetime] = None,
) -> RevokedToken:
    """Add a token jti to the revoked list."""
    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    revoked = RevokedToken(
        jti=jti,
        token_type=token_type,
        user_id=user_id,
        expires_at=expires_at,
    )
    db.add(revoked)
    db.commit()
    db.refresh(revoked)
    return revoked

