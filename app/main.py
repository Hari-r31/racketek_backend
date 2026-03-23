"""
Racketek Outlet — FastAPI Backend
Main application entry point

Fixes applied
-------------
C3  — Removed Base.metadata.create_all(); Alembic is sole migration tool.
H7  — API docs (Swagger/ReDoc/OpenAPI JSON) disabled when DEBUG=False.
M5  — SecurityHeadersMiddleware injects HSTS, X-Frame-Options, CSP, etc.
C2  — docs disabled via DEBUG flag guard.
M2  — Cloudinary configured once at startup (not per request).
"""
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.api.v1.router import api_router

logger = logging.getLogger(__name__)

# ── Optional Sentry integration ───────────────────────────────────────────────
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            traces_sample_rate=0.2,
        )
        logger.info("[Sentry] Initialized for environment: %s", settings.ENVIRONMENT)
    except ImportError:
        logger.warning("[Sentry] sentry-sdk not installed; skipping Sentry init.")

# ── M2 FIX: configure Cloudinary once at startup ─────────────────────────────
if settings.CLOUDINARY_CLOUD_NAME:
    import cloudinary
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
    )
    logger.info("[Cloudinary] Configured for cloud: %s", settings.CLOUDINARY_CLOUD_NAME)

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── H7 FIX: disable docs in production ───────────────────────────────────────
_docs_url    = "/api/docs"     if settings.DEBUG else None
_redoc_url   = "/api/redoc"    if settings.DEBUG else None
_openapi_url = "/api/openapi.json" if settings.DEBUG else None

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-ready eCommerce API for Racketek Outlet",
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

# ── Rate limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── M5 FIX: Security headers middleware ──────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects production security headers on every response.

    HSTS      — browser caches HTTPS-only requirement for 1 year
    X-Content-Type-Options — prevents MIME-sniffing attacks
    X-Frame-Options        — prevents clickjacking (allow-from our origin)
    CSP                    — restricts resource origins; tuned for Next.js + Razorpay + Google
    Referrer-Policy        — limits referrer info sent to third parties
    Permissions-Policy     — disables unused browser features
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Only add HSTS in production (requires HTTPS)
        if settings.cookie_secure:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(self)"
        )
        # CSP: tightened for this stack — adjust if you add more CDNs
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://accounts.google.com https://checkout.razorpay.com 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https://res.cloudinary.com https://lh3.googleusercontent.com; "
            "font-src 'self'; "
            "connect-src 'self' https://api.razorpay.com https://accounts.google.com; "
            "frame-src https://api.razorpay.com https://accounts.google.com; "
            "object-src 'none'; "
            "base-uri 'self';"
        )

        return response


app.add_middleware(SecurityHeadersMiddleware)

# ── CORS ──────────────────────────────────────────────────────────────────────
logger.info("[CORS] Allowed origins: %s", settings.ALLOWED_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Set-Cookie"],
)

# ── API routes ────────────────────────────────────────────────────────────────
# C3 FIX: Base.metadata.create_all() has been REMOVED.
# Run `alembic upgrade head` before starting the server.
app.include_router(api_router, prefix="/api/v1")


# ── Health endpoints ──────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {"message": "Racketek Outlet API is running", "version": settings.APP_VERSION}


@app.get("/api/health", tags=["Health"])
def health_check():
    # H6 FIX: removed cors_origins from health response
    return {"status": "healthy", "app": settings.APP_NAME}
