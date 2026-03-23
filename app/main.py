"""
Racketek Outlet - FastAPI Backend
Main application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.api.v1.router import api_router
from app.db.session import engine
from app.db.base import Base

# Create tables on startup (use Alembic in production)
Base.metadata.create_all(bind=engine)

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-ready eCommerce API for Racketek Outlet",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Log parsed origins at startup so misconfiguration is immediately visible.
# If an origin is missing here, CORS will block it silently in the browser.
print(f"\n[CORS] Allowed origins ({len(settings.ALLOWED_ORIGINS)}):")
for origin in settings.ALLOWED_ORIGINS:
    print(f"       • {origin}")
print()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,   # Required: frontend sends httpOnly cookie on refresh
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Set-Cookie"],  # Allow browser to read Set-Cookie on refresh response
)

# Include all API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def root():
    return {"message": "Racketek Outlet API is running", "version": settings.APP_VERSION}


@app.get("/api/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "cors_origins": settings.ALLOWED_ORIGINS,
    }
