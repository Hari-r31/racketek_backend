"""
JWT Authentication & Password Hashing

passlib 1.7.x is incompatible with bcrypt 4.x (AttributeError: __about__).
Fix: call bcrypt directly, no passlib at all.

bcrypt still has a 72-byte input limit, so we SHA-256 + base64 the
password first — output is always exactly 44 bytes, always safe.
"""
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


# ── password helpers ──────────────────────────────────────────────────────────

def _pre(password: str) -> bytes:
    """
    SHA-256 hash + base64-encode the password.
    Returns exactly 44 ASCII bytes — always within bcrypt's 72-byte limit.
    """
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)          # 44 bytes, pure ASCII


def get_password_hash(password: str) -> str:
    hashed = bcrypt.hashpw(_pre(password), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(_pre(plain_password), hashed_password.encode("utf-8"))


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
