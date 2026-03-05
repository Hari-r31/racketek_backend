"""
OTP Service — generate, store (hashed), send via email/SMS, verify

All OTPs are:
  - 6-digit numeric codes
  - Valid for 10 minutes
  - Stored as SHA-256 hash (never plaintext) in the DB
  - Rate-limited: max 3 sends per 10 min per user (enforced at endpoint level)
"""
import random
import hashlib
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

OTP_EXPIRE_MINUTES = 10


# ── Core helpers ──────────────────────────────────────────────────────────────

def generate_otp() -> str:
    """Return a 6-digit zero-padded numeric OTP."""
    return f"{random.SystemRandom().randint(0, 999999):06d}"


def hash_otp(otp: str) -> str:
    """SHA-256 hash an OTP before storing it."""
    return hashlib.sha256(otp.encode()).hexdigest()


def otp_expiry() -> datetime:
    return datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)


def verify_otp(plain_otp: str, stored_hash: str | None, expiry: datetime | None) -> bool:
    """Return True if the OTP matches and hasn't expired."""
    if not stored_hash or not expiry:
        return False
    if datetime.utcnow() > expiry:
        return False
    return hashlib.sha256(plain_otp.encode()).hexdigest() == stored_hash


# ── Email OTP ─────────────────────────────────────────────────────────────────

def send_otp_email(to_email: str, name: str, otp: str, purpose: str = "verification") -> None:
    """
    Send an OTP email.
    In DEBUG mode — prints to console instead of sending.
    """
    subject_map = {
        "verification":     "Your Email Verification Code",
        "forgot_password":  "Your Password Reset Code",
    }
    subject = subject_map.get(purpose, "Your OTP Code")

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:32px">
      <div style="text-align:center;margin-bottom:24px">
        <h1 style="color:#16a34a;font-size:28px;font-weight:900;margin:0">RacketOutlet</h1>
      </div>
      <h2 style="color:#111827;font-size:20px;font-weight:800;margin:0 0 8px">{subject}</h2>
      <p style="color:#6b7280;margin:0 0 24px">Hi {name}, use the code below to complete your request.</p>

      <div style="background:#f9fafb;border:2px dashed #e5e7eb;border-radius:16px;
                  padding:24px;text-align:center;margin:0 0 24px">
        <p style="color:#6b7280;font-size:12px;font-weight:700;
                  text-transform:uppercase;letter-spacing:2px;margin:0 0 8px">Your OTP</p>
        <p style="color:#111827;font-size:40px;font-weight:900;
                  letter-spacing:12px;margin:0;font-family:monospace">{otp}</p>
        <p style="color:#9ca3af;font-size:12px;margin:12px 0 0">
          Expires in <strong>{OTP_EXPIRE_MINUTES} minutes</strong>
        </p>
      </div>

      <p style="color:#9ca3af;font-size:12px;margin:0">
        If you didn't request this, you can safely ignore this email.<br>
        Never share this code with anyone.
      </p>
    </div>"""

    if settings.DEBUG:
        print(f"\n{'='*50}")
        print(f"[EMAIL OTP DEBUG] To: {to_email}")
        print(f"[EMAIL OTP DEBUG] Subject: {subject}")
        print(f"[EMAIL OTP DEBUG] OTP: {otp}")
        print(f"{'='*50}\n")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM_EMAIL, to_email, msg.as_string())
    except Exception as exc:
        print(f"[OTP Email Error] {exc}")
        raise


# ── SMS OTP ───────────────────────────────────────────────────────────────────

def send_otp_sms(to_phone: str, otp: str, purpose: str = "verification") -> None:
    """
    Send an OTP via SMS.
    In DEBUG mode — prints to console.
    In production — uses Twilio (install twilio package and set env vars).

    Required env vars for production:
        TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
    """
    purpose_text = {
        "verification":    "verify your phone number",
        "forgot_password": "reset your password",
    }.get(purpose, "complete your request")

    message = f"Your RacketOutlet OTP to {purpose_text}: {otp}. Valid for {OTP_EXPIRE_MINUTES} minutes. Do not share."

    if settings.DEBUG:
        print(f"\n{'='*50}")
        print(f"[SMS OTP DEBUG] To: {to_phone}")
        print(f"[SMS OTP DEBUG] OTP: {otp}")
        print(f"[SMS OTP DEBUG] Message: {message}")
        print(f"{'='*50}\n")
        return

    # ── Twilio (production) ──────────────────────────────────────────────────
    try:
        from twilio.rest import Client  # type: ignore
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=to_phone,
        )
    except ImportError:
        print("[SMS OTP] Twilio not installed. Run: pip install twilio")
        raise RuntimeError("SMS provider not configured. Install twilio and set TWILIO_* env vars.")
    except Exception as exc:
        print(f"[SMS OTP Error] {exc}")
        raise
