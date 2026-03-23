"""
JWT Authentication & Password Hashing

Fixes applied:
  - M9: decode_token now distinguishes expired vs invalid tokens.
  - H3: create_oauth_password() generates a cryptographically random password
        for Google OAuth users so no attacker can reconstruct it from the sub.
"""
import hashlib
import base64
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal

import bcrypt
from jose import JWTError, ExpiredSignatureError, jwt

from app.core.config import settings

# ── TokenDecodeResult ─────────────────────────────────────────────────────────

TokenDecodeStatus = Literal["ok", "expired", "invalid"]


class TokenDecodeResult:
    __slots__ = ("status", "payload")

    def __init__(self, status: TokenDecodeStatus, payload: Optional[dict] = None):
        self.status = status
        self.payload = payload

    @property
    def ok(self) -> bool:
        return self.status == "ok"


# ── password helpers ──────────────────────────────────────────────────────────

def _pre(password: str) -> bytes:
    """
    SHA-256 + base64-encode the password to keep it within bcrypt's 72-byte limit.
    Returns exactly 44 ASCII bytes.
    """
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def get_password_hash(password: str) -> str:
    hashed = bcrypt.hashpw(_pre(password), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(_pre(plain_password), hashed_password.encode("utf-8"))


def create_oauth_password() -> str:
    """
    H3 FIX: Generate a cryptographically random placeholder password for
    OAuth users. This value is never used for authentication — OAuth users
    must authenticate via their provider. It exists only because
    hashed_password is NOT NULL in the schema.

    Using secrets.token_hex(32) produces 64 random hex chars, which is
    impossible to reconstruct from any public information about the user.
    """
    return secrets.token_hex(32)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """
    Legacy helper retained for call-sites that only need the payload or None.
    Use decode_token_detailed() where you need to distinguish expired vs invalid.
    """
    result = decode_token_detailed(token)
    return result.payload if result.ok else None


def decode_token_detailed(token: str) -> TokenDecodeResult:
    """
    M9 FIX: Decode a JWT and return a structured result so callers can
    distinguish an expired token (→ attempt refresh) from a truly invalid
    token (→ clear state, do not retry).

    Returns:
      status="ok"      payload=<claims dict>   — valid token
      status="expired" payload=None            — valid structure but past exp
      status="invalid" payload=None            — malformed / wrong signature
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return TokenDecodeResult("ok", payload)
    except ExpiredSignatureError:
        return TokenDecodeResult("expired")
    except JWTError:
        return TokenDecodeResult("invalid")
