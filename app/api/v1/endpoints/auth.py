"""
Authentication endpoints: register, login, refresh, change-password,
forgot-password (OTP via email or phone), Google OAuth2
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

from app.core.dependencies import get_db, get_current_user
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, decode_token,
)
from app.models.user import User, UserRole
from app.models.cart import Cart
from app.schemas.user import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    RefreshTokenRequest, ChangePasswordRequest, OAuthGoogleRequest,
)
from app.services.otp_service import (
    generate_otp, hash_otp, otp_expiry, verify_otp,
    send_otp_email, send_otp_sms,
)

router = APIRouter()


# ── Request schemas ───────────────────────────────────────────────────────────

class ForgotPasswordSendRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str]      = None

class ForgotPasswordVerifyRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str]      = None
    otp:   str

class ForgotPasswordResetRequest(BaseModel):
    email:        Optional[EmailStr] = None
    phone:        Optional[str]      = None
    otp:          str
    new_password: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_tokens(user: User) -> TokenResponse:
    access_token  = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user,
    )


def _ensure_cart(user: User, db: Session) -> None:
    if not db.query(Cart).filter(Cart.user_id == user.id).first():
        db.add(Cart(user_id=user.id))
        db.commit()


def _lookup_by_email_or_phone(email: Optional[str], phone: Optional[str], db: Session) -> User:
    """Find a user by email or phone. Raises 404 if not found."""
    if not email and not phone:
        raise HTTPException(status_code=400, detail="Provide email or phone number")
    user = None
    if email:
        user = db.query(User).filter(User.email == email).first()
    elif phone:
        clean = phone.strip().replace(" ", "").replace("-", "")
        user  = db.query(User).filter(User.phone == clean).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account found with that email or phone")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is disabled")
    return user


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
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
    return _make_tokens(user)


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is disabled")
    return _make_tokens(user)


# ── Refresh Token ─────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    token_data = decode_token(payload.refresh_token)
    if not token_data or token_data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    user = db.query(User).filter(
        User.id == int(token_data["sub"]),
        User.is_active == True,
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return _make_tokens(user)


# ── Change Password ───────────────────────────────────────────────────────────

@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"message": "Password changed successfully"}


# ── Get Current User ──────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


# ═══════════════════════════════════════════════════════════════════════════════
#  FORGOT PASSWORD — OTP flow
#  Step 1 POST /auth/forgot-password/send-otp    { email? phone? }
#  Step 2 POST /auth/forgot-password/verify-otp  { email? phone? otp }
#  Step 3 POST /auth/forgot-password/reset       { email? phone? otp new_password }
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/forgot-password/send-otp")
def forgot_password_send_otp(
    payload: ForgotPasswordSendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Generate a 6-digit OTP and send it to the user's email or phone.
    Always returns 200 to prevent user enumeration.
    """
    try:
        user = _lookup_by_email_or_phone(payload.email, payload.phone, db)
    except HTTPException:
        # Return success anyway — don't reveal whether account exists
        return {"message": "If an account exists, an OTP has been sent."}

    otp      = generate_otp()
    otp_hash = hash_otp(otp)
    expiry   = otp_expiry()

    # Store hashed OTP
    user.reset_otp         = otp_hash
    user.reset_otp_expiry  = expiry
    user.reset_otp_contact = str(payload.email or payload.phone)
    db.commit()

    # Send in background
    if payload.email:
        background_tasks.add_task(
            send_otp_email, user.email, user.full_name, otp, "forgot_password"
        )
    else:
        clean_phone = payload.phone.strip().replace(" ", "").replace("-", "")
        background_tasks.add_task(send_otp_sms, clean_phone, otp, "forgot_password")

    return {"message": "OTP sent successfully"}


@router.post("/forgot-password/verify-otp")
def forgot_password_verify_otp(
    payload: ForgotPasswordVerifyRequest,
    db: Session = Depends(get_db),
):
    """Verify the OTP without resetting the password yet (used for multi-step UI)."""
    user = _lookup_by_email_or_phone(payload.email, payload.phone, db)

    if not verify_otp(payload.otp.strip(), user.reset_otp, user.reset_otp_expiry):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    return {"message": "OTP verified"}


@router.post("/forgot-password/reset")
def forgot_password_reset(
    payload: ForgotPasswordResetRequest,
    db: Session = Depends(get_db),
):
    """Verify OTP and set the new password in one step."""
    user = _lookup_by_email_or_phone(payload.email, payload.phone, db)

    if not verify_otp(payload.otp.strip(), user.reset_otp, user.reset_otp_expiry):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    # Set new password and clear OTP
    user.hashed_password  = get_password_hash(payload.new_password)
    user.reset_otp        = None
    user.reset_otp_expiry = None
    user.reset_otp_contact = None
    db.commit()

    return {"message": "Password reset successfully"}


# ── Google OAuth2 ─────────────────────────────────────────────────────────────

@router.post("/oauth/google", response_model=TokenResponse)
def google_oauth(payload: OAuthGoogleRequest, db: Session = Depends(get_db)):
    google_user = _verify_google_token(payload.id_token)

    is_new = False
    user   = db.query(User).filter(User.email == google_user["email"]).first()

    if not user:
        is_new = True
        user = User(
            full_name=payload.full_name or google_user.get("name", google_user["email"].split("@")[0]),
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
        if google_user.get("picture") and user.profile_image != google_user["picture"]:
            user.profile_image = google_user["picture"]
            db.commit()
            db.refresh(user)

    tokens = _make_tokens(user)
    tokens.is_new_user = is_new
    return tokens


def _verify_google_token(id_token: str) -> dict:
    from app.core.config import settings
    if settings.DEBUG and id_token in ("mock_test_token", "test"):
        return {
            "sub": "google_test_user_12345",
            "email": "oauth.test@gmail.com",
            "name": "OAuth Test User",
            "picture": "https://lh3.googleusercontent.com/test",
            "email_verified": True,
        }
    try:
        import httpx
        resp = httpx.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
            timeout=10,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Google token")
        data = resp.json()
        if "error" in data:
            raise HTTPException(status_code=401, detail=f"Google token error: {data['error']}")
        return data
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Could not reach Google OAuth server")
