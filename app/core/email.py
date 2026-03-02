"""
Email sending utilities — works in debug mode (just prints) or sends real SMTP.
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send_smtp(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email via SMTP. Returns True on success."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM_EMAIL, to_email, msg.as_string())
        return True
    except Exception as exc:
        logger.error("Email send failed: %s", exc)
        return False


def send_email_verification_otp(to_email: str, full_name: str, otp: str) -> bool:
    subject   = "Verify your Racketek Outlet email"
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:32px;
                border:1px solid #e5e7eb;border-radius:12px;">
      <h2 style="color:#ea580c;margin-bottom:8px;">Racketek Outlet</h2>
      <p style="color:#374151;">Hi <strong>{full_name}</strong>,</p>
      <p style="color:#374151;">Use the OTP below to verify your email address.
         It expires in <strong>15 minutes</strong>.</p>
      <div style="background:#f3f4f6;border-radius:10px;padding:20px;text-align:center;
                  margin:24px 0;letter-spacing:8px;font-size:32px;font-weight:900;
                  color:#111827;">{otp}</div>
      <p style="color:#6b7280;font-size:13px;">
        If you didn't request this, you can safely ignore this email.
      </p>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0"/>
      <p style="color:#9ca3af;font-size:12px;">Racketek Outlet — India's Premier Sports Store</p>
    </div>
    """

    if settings.DEBUG:
        logger.info("==[ EMAIL VERIFICATION OTP ]==  to=%s  otp=%s", to_email, otp)
        print(f"\n✉️  Verification OTP for {to_email}: {otp}\n")
        return True

    return _send_smtp(to_email, subject, html_body)


def send_password_reset_email(to_email: str, full_name: str, reset_link: str) -> bool:
    subject   = "Reset your Racketek Outlet password"
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:32px;
                border:1px solid #e5e7eb;border-radius:12px;">
      <h2 style="color:#ea580c;margin-bottom:8px;">Racketek Outlet</h2>
      <p style="color:#374151;">Hi <strong>{full_name}</strong>,</p>
      <p style="color:#374151;">Click the button below to reset your password.
         This link expires in <strong>30 minutes</strong>.</p>
      <a href="{reset_link}" style="display:inline-block;background:#ea580c;color:#fff;
         font-weight:700;text-decoration:none;padding:12px 28px;border-radius:8px;
         margin:20px 0;">Reset Password</a>
      <p style="color:#6b7280;font-size:13px;">
        Or copy this link:<br/>
        <a href="{reset_link}" style="color:#ea580c;word-break:break-all;">{reset_link}</a>
      </p>
      <p style="color:#6b7280;font-size:13px;">
        If you didn't request a password reset, ignore this email.
      </p>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0"/>
      <p style="color:#9ca3af;font-size:12px;">Racketek Outlet — India's Premier Sports Store</p>
    </div>
    """

    if settings.DEBUG:
        logger.info("==[ PASSWORD RESET LINK ]==  to=%s  link=%s", to_email, reset_link)
        print(f"\n🔑  Password reset link for {to_email}:\n    {reset_link}\n")
        return True

    return _send_smtp(to_email, subject, html_body)
