"""
Password hashing and JWT issuance/verification.

This is real, server-side authentication -- not a frontend-only check.
Passwords are hashed with bcrypt directly; tokens are signed JWTs.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt, JWTError
import bcrypt

from app.core.config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    # Bcrypt ki 72-byte limit ko handle karne ke liye truncate karte hain
    password_bytes = password.encode('utf-8')[:72]
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode('utf-8')[:72]
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(subject: str, role: str, extra_claims: dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": subject, "role": role, "exp": expire, "type": "access"}
    if extra_claims:
        to_encode.update(extra_claims)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None