"""
User profile endpoints:
  - GET/PUT  /users/profile
  - POST     /users/change-password
  - POST     /users/send-email-otp        ← new
  - POST     /users/verify-email-otp      ← new
  - POST     /users/send-phone-otp        ← new
  - POST     /users/verify-phone-otp      ← new
  - DELETE   /users/account
  - Admin:   GET /users, PATCH /{id}/block, PATCH /{id}/role
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

from app.core.dependencies import get_db, get_current_user, require_admin
from app.core.security import verify_password, get_password_hash
from app.models.user import User, UserRole
from app.schemas.user import UserResponse, UserUpdate
from app.services.otp_service import (
    generate_otp, hash_otp, otp_expiry, verify_otp,
    send_otp_email, send_otp_sms,
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
    updateable = ["full_name", "phone", "profile_image",
                  "date_of_birth", "address_line1", "city", "state", "pincode"]
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
#  POST /users/send-email-otp    — generate & send OTP to user's email
#  POST /users/verify-email-otp  — verify OTP and mark email as verified
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/send-email-otp")
def send_email_otp(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a 6-digit OTP to the authenticated user's email address."""
    if not current_user.email:
        raise HTTPException(status_code=400, detail="No email address on your account")

    otp      = generate_otp()
    otp_hash = hash_otp(otp)
    expiry   = otp_expiry()

    current_user.email_otp        = otp_hash
    current_user.email_otp_expiry = expiry
    db.commit()

    background_tasks.add_task(
        send_otp_email,
        current_user.email,
        current_user.full_name,
        otp,
        "verification",
    )

    return {"message": f"OTP sent to {current_user.email}"}


@router.post("/verify-email-otp", response_model=UserResponse)
def verify_email_otp(
    payload: VerifyOtpRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify the OTP and mark the user's email as verified."""
    if not verify_otp(payload.otp.strip(), current_user.email_otp, current_user.email_otp_expiry):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    current_user.is_email_verified = True
    current_user.email_otp         = None
    current_user.email_otp_expiry  = None
    current_user.updated_at        = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    return current_user


# ═══════════════════════════════════════════════════════════════════════════════
#  PHONE VERIFICATION via OTP
#  POST /users/send-phone-otp    — generate & send OTP to user's phone
#  POST /users/verify-phone-otp  — verify OTP and mark phone as verified
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/send-phone-otp")
def send_phone_otp(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a 6-digit OTP SMS to the authenticated user's phone number."""
    if not current_user.phone:
        raise HTTPException(
            status_code=400,
            detail="No phone number on your account. Add one in your profile first.",
        )

    otp      = generate_otp()
    otp_hash = hash_otp(otp)
    expiry   = otp_expiry()

    current_user.phone_otp        = otp_hash
    current_user.phone_otp_expiry = expiry
    db.commit()

    background_tasks.add_task(send_otp_sms, current_user.phone, otp, "verification")

    return {"message": f"OTP sent to {current_user.phone}"}


@router.post("/verify-phone-otp", response_model=UserResponse)
def verify_phone_otp(
    payload: VerifyOtpRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify the OTP and mark the user's phone as verified."""
    if not verify_otp(payload.otp.strip(), current_user.phone_otp, current_user.phone_otp_expiry):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    current_user.is_phone_verified = True
    current_user.phone_otp         = None
    current_user.phone_otp_expiry  = None
    current_user.updated_at        = datetime.utcnow()
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
    if current_user.role in [UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Super admin accounts cannot be deleted this way")
    db.delete(current_user)
    db.commit()
    return {"message": "Account deleted successfully"}


# ── Legacy token-based email verification (kept for backwards compat) ─────────

@router.post("/send-verification-email")
def send_verification_email(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deprecated: use /send-email-otp instead. Kept for backwards compat."""
    from datetime import timedelta
    from app.core.security import create_access_token
    from app.core.config import settings

    if current_user.is_email_verified:
        raise HTTPException(status_code=400, detail="Email is already verified")

    token = create_access_token(
        data={"sub": str(current_user.id), "purpose": "email_verification"},
        expires_delta=timedelta(hours=24),
    )
    verify_url = f"{settings.FRONTEND_URL}/account/verify-email?token={token}"

    if settings.DEBUG:
        return {
            "message": "Verification email sent (debug — URL returned directly)",
            "verify_url": verify_url,
        }

    background_tasks.add_task(
        _send_legacy_verification_email, current_user.email, current_user.full_name, verify_url
    )
    return {"message": "Verification email sent — please check your inbox"}


@router.post("/verify-email")
def verify_email_legacy(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deprecated: use /verify-email-otp instead."""
    from app.core.security import decode_token
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")
    if payload.get("purpose") != "email_verification":
        raise HTTPException(status_code=400, detail="Invalid token purpose")
    if int(payload.get("sub", 0)) != current_user.id:
        raise HTTPException(status_code=400, detail="Token does not match your account")
    if current_user.is_email_verified:
        return {"message": "Email already verified"}
    current_user.is_email_verified = True
    current_user.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Email verified successfully"}


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
    return {"message": f"User {'activated' if user.is_active else 'blocked'}", "is_active": user.is_active}


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


# ── Legacy email helper ───────────────────────────────────────────────────────

def _send_legacy_verification_email(email: str, name: str, verify_url: str):
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from app.core.config import settings

        html = f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px">
          <h2 style="color:#16a34a">Verify your email</h2>
          <p>Hi {name}, click below to verify your email address.</p>
          <a href="{verify_url}"
             style="display:inline-block;background:#16a34a;color:#fff;
                    font-weight:700;padding:12px 28px;border-radius:12px;text-decoration:none">
            Verify Email
          </a>
          <p style="color:#9ca3af;font-size:12px;margin-top:24px">
            Link expires in 24 hours.
          </p>
        </div>"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Verify your Racketek Outlet email"
        msg["From"]    = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
        msg["To"]      = email
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM_EMAIL, email, msg.as_string())
    except Exception as exc:
        print(f"[Email error] {exc}")
