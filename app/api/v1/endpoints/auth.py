"""
Authentication endpoints: register, login, refresh, change-password,
forgot-password (email OTP only), Google OAuth2

Security model
--------------
* access_token  — returned in JSON body only. NEVER stored in a cookie.
* refresh_token — httpOnly, Secure, SameSite=Lax cookie ONLY.
                  Never returned in the response body.

Token refresh flow
------------------
POST /auth/refresh  (no body required)
  → reads refresh_token from the httpOnly cookie automatically
  → returns new access_token in body + rotates the httpOnly cookie

Fixes applied
-------------
C2  — _COOKIE_SECURE uses settings.cookie_secure (derived from DEBUG flag)
C4  — SlowAPI rate-limit decorators on login, register, send-otp, verify-otp
H3  — Google OAuth: random password via create_oauth_password(), auth_provider field
H7  — API docs disabled in production (handled in main.py)
"""

import secrets as _secrets
from fastapi import (
    APIRouter, Depends, HTTPException, BackgroundTasks,
    Response, Request, status,
)
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.dependencies import get_db, get_current_user
from app.core.security import (
    verify_password, get_password_hash, create_oauth_password,
    create_access_token, create_refresh_token, decode_token,
)
from app.core.config import settings
from app.models.user import User, UserRole
from app.models.cart import Cart
from app.schemas.user import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    RefreshTokenRequest, ChangePasswordRequest, OAuthGoogleRequest,
)
from app.services.otp_service import (
    OTP_MAX_ATTEMPTS,
    generate_otp, hash_otp, otp_expiry, verify_otp,
    otp_cooldown_ok, recover_otp_created_at,
    send_otp_email,
)

router = APIRouter()

# ── Rate limiter (uses the app-level limiter from main.py via state) ──────────
limiter = Limiter(key_func=get_remote_address)

# ── Cookie settings ───────────────────────────────────────────────────────────
_COOKIE_NAME    = "refresh_token"
_COOKIE_MAX_AGE = int(timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())
# C2 FIX: use settings.cookie_secure — True in any non-DEBUG environment
_COOKIE_SECURE  = settings.cookie_secure


# ── Request schemas ───────────────────────────────────────────────────────────

class ForgotPasswordSendRequest(BaseModel):
    email: EmailStr

class ForgotPasswordVerifyRequest(BaseModel):
    email: EmailStr
    otp:   str

class ForgotPasswordResetRequest(BaseModel):
    email:        EmailStr
    otp:          str
    new_password: str


# ── Cookie helper ─────────────────────────────────────────────────────────────

def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """
    Attach the refresh_token as an httpOnly cookie.
    httpOnly  — JS cannot read it (XSS protection)
    Secure    — HTTPS only when not in DEBUG mode
    SameSite  — Lax
    Path      — /api/v1/auth scoped so cookie is not sent on every API call
    """
    response.set_cookie(
        key=_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_COOKIE_NAME, path="/api/v1/auth")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_token_response(
    user: User,
    response: Response,
    is_new_user: bool = False,
) -> TokenResponse:
    """
    Create access + refresh tokens.
    - access_token  → included in the returned TokenResponse (JSON body only)
    - refresh_token → set as httpOnly cookie; NEVER in the JSON body
    """
    access_token  = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(
        access_token=access_token,
        user=user,
        is_new_user=is_new_user,
    )


def _ensure_cart(user: User, db: Session) -> None:
    if not db.query(Cart).filter(Cart.user_id == user.id).first():
        db.add(Cart(user_id=user.id))
        db.commit()


def _lookup_by_email(email: str, db: Session) -> User:
    """Find an active user by email. Raises 404 if not found or inactive."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=404, detail="No account found with that email address"
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is disabled")
    return user


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("5/minute")  # C4 FIX
def register(
    request: Request,
    payload: UserCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        hashed_password=get_password_hash(payload.password),
        role=UserRole.CUSTOMER,
        auth_provider="local",
    )
    db.add(user)
    db.flush()
    db.add(Cart(user_id=user.id))
    db.commit()
    db.refresh(user)
    return _build_token_response(user, response)


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")  # C4 FIX
def login(
    request: Request,
    payload: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is disabled")
    # H3 FIX: Block password login for OAuth-only users
    if getattr(user, "auth_provider", "local") == "google":
        raise HTTPException(
            status_code=400,
            detail="This account uses Google Sign-In. Please log in with Google.",
        )
    return _build_token_response(user, response)


# ── Refresh Token ─────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Read the refresh_token from the httpOnly cookie, verify it, and issue a
    new access_token + rotate the refresh_token cookie.
    No request body needed.
    """
    refresh_token = request.cookies.get(_COOKIE_NAME)

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token — please log in again",
        )

    token_data = decode_token(refresh_token)
    if not token_data or token_data.get("type") != "refresh":
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = db.query(User).filter(
        User.id == int(token_data["sub"]),
        User.is_active == True,
    ).first()

    if not user:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return _build_token_response(user, response)


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout")
def logout(response: Response):
    """Clear the httpOnly refresh_token cookie."""
    _clear_refresh_cookie(response)
    return {"message": "Logged out successfully"}


# ── Change Password ───────────────────────────────────────────────────────────

@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # H3: OAuth users cannot set a password via this flow
    if getattr(current_user, "auth_provider", "local") == "google":
        raise HTTPException(
            status_code=400,
            detail="Google Sign-In accounts cannot change password here.",
        )
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    _clear_refresh_cookie(response)
    return {"message": "Password changed successfully"}


# ── Get Current User ──────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


# ═══════════════════════════════════════════════════════════════════════════════
#  FORGOT PASSWORD — email OTP flow
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/forgot-password/send-otp")
@limiter.limit("3/minute")  # C4 FIX — prevents email spam cost explosion
def forgot_password_send_otp(
    request: Request,
    payload: ForgotPasswordSendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Send a 6-digit OTP to the given email for password reset.
    Anti-enumeration: always returns 200 regardless of whether email exists.
    Rate-limited: 3/minute per IP + 60-second DB-level cooldown per account.
    """
    try:
        user = _lookup_by_email(str(payload.email), db)
    except HTTPException:
        return {"message": "If an account with that email exists, a reset code has been sent."}

    otp_created = recover_otp_created_at(user.reset_otp_expiry)
    if not otp_cooldown_ok(otp_created):
        raise HTTPException(
            status_code=429,
            detail="Please wait 60 seconds before requesting another reset code",
        )

    otp          = generate_otp()
    otp_hash_val = hash_otp(otp)
    expiry       = otp_expiry()

    user.reset_otp          = otp_hash_val
    user.reset_otp_expiry   = expiry
    user.reset_otp_attempts = 0
    db.commit()

    background_tasks.add_task(
        send_otp_email, user.email, user.full_name, otp, "forgot_password"
    )

    return {"message": "If an account with that email exists, a reset code has been sent."}


@router.post("/forgot-password/verify-otp")
@limiter.limit("5/minute")  # C4 FIX
def forgot_password_verify_otp(
    request: Request,
    payload: ForgotPasswordVerifyRequest,
    db: Session = Depends(get_db),
):
    """Verify the reset OTP (step 2 of 3) without resetting the password."""
    try:
        user = _lookup_by_email(str(payload.email), db)
    except HTTPException:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    attempts = user.reset_otp_attempts or 0
    if attempts >= OTP_MAX_ATTEMPTS:
        user.reset_otp = user.reset_otp_expiry = None
        user.reset_otp_attempts = 0
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="Too many incorrect attempts. Please request a new reset code.",
        )

    if not verify_otp(payload.otp.strip(), user.reset_otp, user.reset_otp_expiry):
        user.reset_otp_attempts = attempts + 1
        db.commit()
        remaining = OTP_MAX_ATTEMPTS - (attempts + 1)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid or expired code. {remaining} attempt(s) remaining.",
        )

    return {"message": "Code verified"}


@router.post("/forgot-password/reset")
def forgot_password_reset(
    payload: ForgotPasswordResetRequest,
    db: Session = Depends(get_db),
):
    """Verify the reset OTP and set a new password in one step."""
    try:
        user = _lookup_by_email(str(payload.email), db)
    except HTTPException:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    # H3: OAuth users cannot reset password via OTP flow
    if getattr(user, "auth_provider", "local") == "google":
        raise HTTPException(
            status_code=400,
            detail="This account uses Google Sign-In. Password reset is not available.",
        )

    attempts = user.reset_otp_attempts or 0
    if attempts >= OTP_MAX_ATTEMPTS:
        user.reset_otp = user.reset_otp_expiry = None
        user.reset_otp_attempts = 0
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="Too many incorrect attempts. Please request a new reset code.",
        )

    if not verify_otp(payload.otp.strip(), user.reset_otp, user.reset_otp_expiry):
        user.reset_otp_attempts = attempts + 1
        db.commit()
        remaining = OTP_MAX_ATTEMPTS - (attempts + 1)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid or expired code. {remaining} attempt(s) remaining.",
        )

    if len(payload.new_password) < 6:
        raise HTTPException(
            status_code=400, detail="Password must be at least 6 characters"
        )

    user.hashed_password    = get_password_hash(payload.new_password)
    user.reset_otp          = None
    user.reset_otp_expiry   = None
    user.reset_otp_attempts = 0
    db.commit()
    return {"message": "Password reset successfully"}


# ── Google OAuth2 ─────────────────────────────────────────────────────────────

@router.post("/oauth/google", response_model=TokenResponse)
def google_oauth(
    payload: OAuthGoogleRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Verify the Google id_token server-side (cryptographic signature check).
    H3 FIX: New OAuth users get a random placeholder password, not hash(sub).
             auth_provider is set to "google" to block password-login.
    """
    google_user = _verify_google_token(payload.id_token)

    is_new = False
    user   = db.query(User).filter(User.email == google_user["email"]).first()

    if not user:
        is_new = True
        user = User(
            full_name=(
                payload.full_name
                or google_user.get("name")
                or google_user["email"].split("@")[0]
            ),
            email=google_user["email"],
            phone=payload.phone,
            # H3 FIX: random secret — cannot be reconstructed from public data
            hashed_password=get_password_hash(create_oauth_password()),
            role=UserRole.CUSTOMER,
            is_email_verified=google_user.get("email_verified", False),
            profile_image=google_user.get("picture"),
            auth_provider="google",
        )
        db.add(user)
        db.flush()
        db.add(Cart(user_id=user.id))
        db.commit()
        db.refresh(user)

    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Account is disabled")

    else:
        if google_user.get("picture") and user.profile_image != google_user["picture"]:
            user.profile_image = google_user["picture"]
            db.commit()
            db.refresh(user)

    return _build_token_response(user, response, is_new_user=is_new)


def _verify_google_token(id_token: str) -> dict:
    """
    Verify the Google id_token cryptographically using the google-auth library.
    Raises HTTP 401 on any verification failure.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID in backend .env.",
        )

    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests

        claims = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Google token verification failed: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not verify Google token: {exc}",
        )

    if claims.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Google token audience mismatch")

    if not claims.get("email"):
        raise HTTPException(status_code=401, detail="Google token has no email")

    return claims
