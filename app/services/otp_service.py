"""
OTP Service — email-only, production-grade

Security properties:
  - 6-digit numeric OTP
  - 5-minute expiry (enforced at verify time)
  - Stored as SHA-256 hash — never plaintext
  - Max 5 verification attempts before lockout (caller enforces)
  - 60-second cooldown between sends (caller enforces via otp_cooldown_ok())
  - OTP invalidated on successful verification
  - No SMS / Twilio integration — email only
"""
import random
import hashlib
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

OTP_EXPIRE_MINUTES = 5
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_MAX_ATTEMPTS = 5


# ── Core helpers ──────────────────────────────────────────────────────────────

def generate_otp() -> str:
    """Return a cryptographically random 6-digit zero-padded OTP."""
    return f"{random.SystemRandom().randint(0, 999999):06d}"


def hash_otp(otp: str) -> str:
    """SHA-256 hash an OTP before storing it."""
    return hashlib.sha256(otp.encode()).hexdigest()


def otp_expiry() -> datetime:
    """Return the expiry timestamp for a freshly generated OTP."""
    return datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)


def verify_otp(plain_otp: str, stored_hash: str | None, expiry: datetime | None) -> bool:
    """
    Return True only if:
      1. A hash and expiry exist
      2. The current time is before expiry
      3. SHA-256(plain_otp) == stored_hash
    Constant-time comparison via hmac.compare_digest.
    """
    import hmac
    if not stored_hash or not expiry:
        return False
    if datetime.utcnow() > expiry:
        return False
    candidate = hashlib.sha256(plain_otp.encode()).hexdigest()
    # compare_digest prevents timing attacks
    return hmac.compare_digest(candidate, stored_hash)


def otp_cooldown_ok(created_at: datetime | None) -> bool:
    """
    Return True if enough time has passed since the last OTP was sent.
    Pass the timestamp when the current OTP hash was set on the user row.
    The User model stores email_otp_expiry; subtract OTP_EXPIRE_MINUTES to
    recover the creation time.
    """
    if created_at is None:
        return True
    elapsed = (datetime.utcnow() - created_at).total_seconds()
    return elapsed >= OTP_RESEND_COOLDOWN_SECONDS


def recover_otp_created_at(expiry: datetime | None) -> datetime | None:
    """
    Recover the approximate OTP creation time from its expiry timestamp.
    Used to enforce the resend cooldown without an extra DB column.
    """
    if expiry is None:
        return None
    return expiry - timedelta(minutes=OTP_EXPIRE_MINUTES)


# ── Email sending ─────────────────────────────────────────────────────────────

def send_otp_email(to_email: str, name: str, otp: str, purpose: str = "verification") -> None:
    """
    Send a 6-digit OTP to `to_email`.

    In DEBUG mode: prints to console (no SMTP required for local dev).
    In production: sends via SMTP using credentials from settings.

    `purpose` controls the subject line and body copy:
      - "verification"    → Email Verification
      - "forgot_password" → Password Reset
      - "email_change"    → Email Address Change
    """
    subject_map = {
        "verification":    "Your Email Verification Code — Racketek Outlet",
        "forgot_password": "Your Password Reset Code — Racketek Outlet",
        "email_change":    "Confirm Your New Email — Racketek Outlet",
    }
    subject = subject_map.get(purpose, "Your OTP Code — Racketek Outlet")

    action_map = {
        "verification":    "verify your email address",
        "forgot_password": "reset your password",
        "email_change":    "confirm your new email address",
    }
    action = action_map.get(purpose, "complete your request")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:40px 0">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:16px;overflow:hidden;
                    box-shadow:0 4px 24px rgba(0,0,0,0.08)">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#16a34a,#15803d);
                     padding:28px 32px;text-align:center">
            <h1 style="margin:0;color:#ffffff;font-size:24px;
                       font-weight:900;letter-spacing:-0.5px">
              🏸 Racketek Outlet
            </h1>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px">
            <h2 style="margin:0 0 8px;color:#111827;font-size:20px;font-weight:800">
              {subject.split(" — ")[0]}
            </h2>
            <p style="margin:0 0 24px;color:#6b7280;font-size:15px;line-height:1.5">
              Hi <strong>{name}</strong>, use the one-time code below to {action}.
            </p>

            <!-- OTP box -->
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="background:#f9fafb;border:2px dashed #d1fae5;
                           border-radius:12px;padding:24px;text-align:center">
                  <p style="margin:0 0 6px;color:#6b7280;font-size:11px;
                             font-weight:700;text-transform:uppercase;letter-spacing:2px">
                    One-Time Code
                  </p>
                  <p style="margin:0;color:#111827;font-size:44px;font-weight:900;
                             letter-spacing:14px;font-family:Courier New,monospace">
                    {otp}
                  </p>
                  <p style="margin:10px 0 0;color:#9ca3af;font-size:12px">
                    Expires in <strong style="color:#ef4444">{OTP_EXPIRE_MINUTES} minutes</strong>
                  </p>
                </td>
              </tr>
            </table>

            <p style="margin:24px 0 0;color:#9ca3af;font-size:12px;line-height:1.6">
              If you did not request this code, you can safely ignore this email.<br>
              <strong>Never share this code with anyone — Racketek will never ask for it.</strong>
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f9fafb;padding:16px 32px;
                     border-top:1px solid #e5e7eb;text-align:center">
            <p style="margin:0;color:#d1d5db;font-size:11px">
              © Racketek Outlet · Hyderabad, India
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    if settings.DEBUG:
        print(f"\n{'='*60}")
        print(f"[EMAIL OTP — DEBUG MODE]")
        print(f"  To      : {to_email}")
        print(f"  Subject : {subject}")
        print(f"  Purpose : {purpose}")
        print(f"  OTP     : {otp}   (expires in {OTP_EXPIRE_MINUTES} min)")
        print(f"{'='*60}\n")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM_EMAIL, to_email, msg.as_string())

    except smtplib.SMTPException as exc:
        # Log and re-raise so the caller can handle it
        print(f"[OTP Email SMTP Error] {exc}")
        raise RuntimeError(f"Failed to send OTP email: {exc}") from exc
    except Exception as exc:
        print(f"[OTP Email Error] {exc}")
        raise
