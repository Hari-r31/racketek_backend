"""
Application settings — loaded from environment variables.

Environment separation:
  Development : DEBUG=True   (set in .env.development)
  Production  : DEBUG=False  (must never be overridden to True on a server)

ENVIRONMENT controls context-aware behaviour (Sentry, log level).
DEBUG is independent so staging can be non-debug and non-production.
"""
from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "Racketek Outlet"
    APP_VERSION: str = "1.0.0"
    # NEVER set True in production — controls cookie Secure flag, SMTP bypass,
    # API docs exposure, and OTP log-to-console behaviour.
    DEBUG: bool = False
    ENVIRONMENT: str = "production"  # development | staging | production
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str

    # ── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Razorpay ─────────────────────────────────────────────────────────────
    RAZORPAY_KEY_ID: str
    RAZORPAY_KEY_SECRET: str
    # Generate in Razorpay Dashboard → Settings → Webhooks → Secret
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # ── Cloudinary ───────────────────────────────────────────────────────────
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # ── Email ────────────────────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: str = "noreply@racketek.com"
    EMAILS_FROM_NAME: str = "Racketek Outlet"

    # ── Google OAuth ─────────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # ── OpenAI ───────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""

    # ── Celery ───────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Sentry (optional) ────────────────────────────────────────────────────
    SENTRY_DSN: str = ""

    # ── CORS ─────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # ── Frontend ─────────────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        case_sensitive = True

        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str):
            if field_name == "ALLOWED_ORIGINS":
                stripped = raw_val.strip()
                if stripped.startswith("["):
                    try:
                        parsed = json.loads(stripped)
                        return [o.strip().rstrip("/") for o in parsed if o.strip()]
                    except json.JSONDecodeError:
                        pass
                return [o.strip().rstrip("/") for o in stripped.split(",") if o.strip()]
            return raw_val

    # ── Derived helpers ───────────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def cookie_secure(self) -> bool:
        """True when running over HTTPS (non-debug production/staging)."""
        return not self.DEBUG


settings = Settings()
