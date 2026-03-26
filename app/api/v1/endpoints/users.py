"""
User profile endpoints:

  GET  /users/profile              — get own profile
  PUT  /users/profile              — update own profile
  POST /users/change-password      — change password (authenticated)
  POST /users/send-email-otp       — send verification OTP to user's email
  POST /users/verify-email-otp     — verify OTP and mark email as verified
  DEL  /users/account              — delete own account

  Admin only:
  GET    /users                    — list all users
  PATCH  /users/{id}/block         — toggle user active state
  PATCH  /users/{id}/role          — change user role

Removed (phone OTP / legacy):
  - POST /users/send-phone-otp
  - POST /users/verify-phone-otp
  - POST /users/send-verification-email  (legacy link-based flow)
  - POST /users/verify-email             (legacy token flow)

Security:
  - Email OTP: 5-min expiry, max 5 attempts, 60-sec resend cooldown
  - All OTP stored as SHA-256 hash — never plaintext
  - Anti-enumeration: same 200 response whether email exists or not
    (for send-email-otp this is not applicable since user is authenticated;
     for forgot-password see auth.py)
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.core.dependencies import get_db, get_current_user, require_admin
from app.core.security import verify_password, get_password_hash
from app.models.user import User
from app.enums import UserRole
from app.schemas.user import UserResponse
from app.services.otp_service import (
    OTP_MAX_ATTEMPTS,
    generate_otp, hash_otp, otp_expiry, verify_otp,
    otp_cooldown_ok, recover_otp_created_at,
    send_otp_email,
)

router = APIRouter()


# ── Request schemas ───────────────────────────────────────────────────────────

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password:     str = Field(..., min_length=6, max_length=100)
    confirm_password: str


class UpdateProfileRequest(BaseModel):
    full_name:     Optional[str] = Field(None, min_length=2, max_length=150)
    phone:         Optional[str] = Field(None, max_length=20)
    profile_image: Optional[str] = None
    date_of_birth: Optional[str] = Field(None, max_length=20)
    address_line1: Optional[str] = Field(None, max_length=300)
    city:          Optional[str] = Field(None, max_length=100)
    state:         Optional[str] = Field(None, max_length=100)
    pincode:       Optional[str] = Field(None, max_length=10)


class DeleteAccountRequest(BaseModel):
    password: str


class VerifyOtpRequest(BaseModel):
    otp: str = Field(..., min_length=6, max_length=6)


# ── Profile ───────────────────────────────────────────────────────────────────

@router.get("/profile", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/profile", response_model=UserResponse)
def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updateable = [
        "full_name", "phone", "profile_image",
        "date_of_birth", "address_line1", "city", "state", "pincode",
    ]
    for field in updateable:
        val = getattr(payload, field, None)
        if val is not None:
            setattr(current_user, field, val)
    current_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    return current_user


# ── Change password ───────────────────────────────────────────────────────────

@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="New passwords do not match")
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must differ from current")
    current_user.hashed_password = get_password_hash(payload.new_password)
    current_user.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Password changed successfully"}


# ═══════════════════════════════════════════════════════════════════════════════
#  EMAIL VERIFICATION via OTP
#
#  POST /users/send-email-otp    — authenticated; sends OTP to own email
#  POST /users/verify-email-otp  — authenticated; verifies OTP, marks email verified
#
#  Security:
#    - 5-minute OTP expiry
#    - 60-second resend cooldown (prevents OTP flooding)
#    - Max 5 incorrect attempts before OTP is invalidated (prevents brute force)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/send-email-otp")
def send_email_otp(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a 6-digit OTP and send it to the authenticated user's email.

    Rate-limited: rejects if the previous OTP was sent less than
    OTP_RESEND_COOLDOWN_SECONDS ago (60 s).
    """
    # Enforce resend cooldown
    otp_created = recover_otp_created_at(current_user.email_otp_expiry)
    if not otp_cooldown_ok(otp_created):
        raise HTTPException(
            status_code=429,
            detail="Please wait 60 seconds before requesting another OTP",
        )

    otp      = generate_otp()
    otp_hash_val = hash_otp(otp)
    expiry   = otp_expiry()

    current_user.email_otp          = otp_hash_val
    current_user.email_otp_expiry   = expiry
    current_user.email_otp_attempts = 0
    current_user.email_otp_purpose  = "verification"
    current_user.updated_at         = datetime.utcnow()
    db.commit()

    background_tasks.add_task(
        send_otp_email,
        current_user.email,
        current_user.full_name,
        otp,
        "verification",
    )

    return {"message": f"Verification code sent to {current_user.email}"}


@router.post("/verify-email-otp", response_model=UserResponse)
def verify_email_otp(
    payload: VerifyOtpRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verify the 6-digit OTP and mark the user's email as verified.

    Attempt tracking: after OTP_MAX_ATTEMPTS failed attempts the OTP is
    invalidated and the user must request a new one.
    """
    # Guard: OTP must have been issued for verification
    if current_user.email_otp_purpose != "verification":
        raise HTTPException(
            status_code=400,
            detail="No pending email verification. Request a new code first.",
        )

    # Attempt limit
    attempts = current_user.email_otp_attempts or 0
    if attempts >= OTP_MAX_ATTEMPTS:
        # Wipe the OTP — force re-send
        current_user.email_otp          = None
        current_user.email_otp_expiry   = None
        current_user.email_otp_attempts = 0
        current_user.email_otp_purpose  = None
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="Too many incorrect attempts. Please request a new verification code.",
        )

    if not verify_otp(payload.otp.strip(), current_user.email_otp, current_user.email_otp_expiry):
        # Increment attempt counter
        current_user.email_otp_attempts = attempts + 1
        db.commit()
        remaining = OTP_MAX_ATTEMPTS - (attempts + 1)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid or expired code. {remaining} attempt(s) remaining.",
        )

    # Success — clear OTP and mark verified
    current_user.is_email_verified  = True
    current_user.email_otp          = None
    current_user.email_otp_expiry   = None
    current_user.email_otp_attempts = 0
    current_user.email_otp_purpose  = None
    current_user.updated_at         = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    return current_user


# ── Delete account ────────────────────────────────────────────────────────────

@router.delete("/account")
def delete_account(
    payload: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Password is incorrect")
    if current_user.role in [UserRole.super_admin]:
        raise HTTPException(
            status_code=403,
            detail="Super admin accounts cannot be deleted via this endpoint",
        )
    db.delete(current_user)
    db.commit()
    return {"message": "Account deleted successfully"}


# ── Admin: list / block / role ────────────────────────────────────────────────

@router.get("", response_model=list[UserResponse])
def list_users(
    skip:  int = 0,
    limit: int = 50,
    db:    Session = Depends(get_db),
    _:     User    = Depends(require_admin),
):
    return db.query(User).offset(skip).limit(limit).all()


@router.patch("/{user_id}/block")
def block_user(
    user_id: int,
    db: Session = Depends(get_db),
    _:  User    = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = not user.is_active
    db.commit()
    return {
        "message": f"User {'activated' if user.is_active else 'blocked'}",
        "is_active": user.is_active,
    }


@router.patch("/{user_id}/role")
def change_role(
    user_id: int,
    role:    UserRole,
    db:      Session = Depends(get_db),
    _:       User    = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = role
    db.commit()
    return {"message": "Role updated", "role": role}
