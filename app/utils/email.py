"""
Email utilities using SMTP
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send an HTML email. Returns True on success."""
    if not settings.SMTP_USER:
        logger.warning("SMTP not configured, skipping email.")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


def send_order_confirmation(to_email: str, order_number: str, total: float):
    html = f"""
    <h2>Thank you for your order!</h2>
    <p>Your order <strong>{order_number}</strong> has been placed successfully.</p>
    <p>Total: <strong>₹{total:.2f}</strong></p>
    <p>We'll notify you when it ships. — Racketek Outlet</p>
    """
    send_email(to_email, f"Order Confirmed – {order_number}", html)


def send_order_status_update(to_email: str, order_number: str, status: str):
    html = f"""
    <h2>Order Update</h2>
    <p>Your order <strong>{order_number}</strong> status has been updated to: <strong>{status.upper()}</strong>.</p>
    <p>— Racketek Outlet</p>
    """
    send_email(to_email, f"Order {order_number} – {status.title()}", html)


def send_password_reset(to_email: str, token: str, frontend_url: str):
    link = f"{frontend_url}/reset-password?token={token}"
    html = f"""
    <h2>Reset Your Password</h2>
    <p>Click the link below to reset your password (valid for 30 minutes):</p>
    <a href="{link}">{link}</a>
    <p>If you didn't request this, ignore this email.</p>
    """
    send_email(to_email, "Reset Your Racketek Password", html)
