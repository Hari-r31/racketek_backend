"""
Authentication endpoints: register, login, refresh, change-password,
forgot-password (email OTP only), Google OAuth2

Security model
--------------
* access_token  — returned in the JSON body (Authorization: Bearer <token>)
* refresh_token — set as an httpOnly, Secure, SameSite=Lax cookie ONLY.
                  It is NEVER returned in the response body.
                  The frontend cannot read it via JavaScript.

Token refresh flow
------------------
POST /auth/refresh  (no body required)
  → reads refresh_token from the httpOnly cookie automatically
  → returns new access_token in body + rotates the httpOnly cookie
"""

from fastapi import (
    APIRouter, Depends, HTTPException, BackgroundTasks,
    Response, Request, status,
)
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta

from app.core.dependencies import get_db, get_current_user
from app.core.security import (
    verify_password, get_password_hash,
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

# Cookie settings
_COOKIE_NAME    = "refresh_token"
_COOKIE_MAX_AGE = int(timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())
# Use secure=True in production (HTTPS). In local dev (DEBUG=True) allow HTTP.
_COOKIE_SECURE  = not settings.DEBUG


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
    Secure    — HTTPS only in production
    SameSite  — Lax: sent on top-level navigations + same-origin requests.
                Use "strict" if you never need cross-origin requests.
    Path      — /api/v1/auth so the cookie is only sent to auth endpoints,
                not leaked on every API call.
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
    response.delete_cookie(
        key=_COOKIE_NAME,
        path="/api/v1/auth",
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_token_response(
    user: User,
    response: Response,
    is_new_user: bool = False,
) -> TokenResponse:
    """
    Create access + refresh tokens.
    - access_token  → included in the returned TokenResponse (JSON body)
    - refresh_token → set as httpOnly cookie; NOT in the JSON body
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
def register(
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
    )
    db.add(user)
    db.flush()
    db.add(Cart(user_id=user.id))
    db.commit()
    db.refresh(user)
    return _build_token_response(user, response)


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is disabled")
    return _build_token_response(user, response)


# ── Refresh Token ─────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Read the refresh_token from the httpOnly cookie (set automatically by
    the browser), verify it, and issue a new access_token + rotate the
    refresh_token cookie.

    No request body is needed or expected.
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

    # Rotate: issue a brand-new refresh_token cookie + new access_token
    return _build_token_response(user, response)


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout")
def logout(response: Response):
    """
    Clear the httpOnly refresh_token cookie.
    The frontend is responsible for discarding the access_token from memory.
    """
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
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    # Invalidate existing sessions by clearing the refresh cookie.
    # User will need to log in again on other devices.
    _clear_refresh_cookie(response)
    return {"message": "Password changed successfully"}


# ── Get Current User ──────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


# ═══════════════════════════════════════════════════════════════════════════════
#  FORGOT PASSWORD — email OTP flow (email-only, no phone)
#  Step 1 POST /auth/forgot-password/send-otp    { email }
#  Step 2 POST /auth/forgot-password/verify-otp  { email, otp }
#  Step 3 POST /auth/forgot-password/reset       { email, otp, new_password }
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/forgot-password/send-otp")
def forgot_password_send_otp(
    payload: ForgotPasswordSendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Send a 6-digit OTP to the given email address for password reset.

    Anti-enumeration: always returns 200 regardless of whether the email
    exists. The OTP is only sent if an active account is found.

    Rate-limited: 60-second resend cooldown per account.
    """
    try:
        user = _lookup_by_email(str(payload.email), db)
    except HTTPException:
        # Don't reveal whether the email exists
        return {"message": "If an account with that email exists, a reset code has been sent."}

    # Enforce resend cooldown
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
def forgot_password_verify_otp(
    payload: ForgotPasswordVerifyRequest,
    db: Session = Depends(get_db),
):
    """
    Verify the reset OTP without resetting the password yet.
    Used by multi-step UI (step 2 of 3).
    """
    try:
        user = _lookup_by_email(str(payload.email), db)
    except HTTPException:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    attempts = user.reset_otp_attempts or 0
    if attempts >= OTP_MAX_ATTEMPTS:
        user.reset_otp          = None
        user.reset_otp_expiry   = None
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
    """
    Verify the reset OTP and set the new password in one step.
    Invalidates the OTP on success.
    """
    try:
        user = _lookup_by_email(str(payload.email), db)
    except HTTPException:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    attempts = user.reset_otp_attempts or 0
    if attempts >= OTP_MAX_ATTEMPTS:
        user.reset_otp          = None
        user.reset_otp_expiry   = None
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
    Verify the Google id_token using the official google-auth library
    (cryptographic signature check against Google's public keys).

    The token is NEVER decoded on the frontend — it is passed here raw
    and verified server-side only.
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
            hashed_password=get_password_hash(google_user["sub"]),
            role=UserRole.CUSTOMER,
            is_email_verified=google_user.get("email_verified", False),
            profile_image=google_user.get("picture"),
        )
        db.add(user)
        db.flush()
        db.add(Cart(user_id=user.id))
        db.commit()
        db.refresh(user)

    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Account is disabled")

    else:
        # Update profile picture if Google has a newer one
        if google_user.get("picture") and user.profile_image != google_user["picture"]:
            user.profile_image = google_user["picture"]
            db.commit()
            db.refresh(user)

    return _build_token_response(user, response, is_new_user=is_new)


def _verify_google_token(id_token: str) -> dict:
    """
    Verify the Google id_token cryptographically using the google-auth library.

    google.oauth2.id_token.verify_oauth2_token():
    - Downloads Google's public keys (cached internally)
    - Verifies the JWT signature
    - Checks expiry, issuer, and audience (client_id)
    - Returns the token claims dict on success

    Raises HTTP 401 on any verification failure.
    Raises HTTP 500 if GOOGLE_CLIENT_ID is not configured.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail=(
                "Google OAuth is not configured. "
                "Set GOOGLE_CLIENT_ID in the backend .env file."
            ),
        )

    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests

        request_obj = google_requests.Request()
        claims = google_id_token.verify_oauth2_token(
            id_token,
            request_obj,
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        # Covers: wrong audience, expired token, bad signature, malformed JWT
        raise HTTPException(
            status_code=401,
            detail=f"Google token verification failed: {exc}",
        )
    except Exception as exc:
        # Network failure fetching Google's public keys, etc.
        raise HTTPException(
            status_code=503,
            detail=f"Could not verify Google token: {exc}",
        )

    # Ensure the token was issued for our client
    if claims.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=401,
            detail="Google token audience mismatch",
        )

    if not claims.get("email"):
        raise HTTPException(
            status_code=401,
            detail="Google token does not contain an email address",
        )

    return claims
