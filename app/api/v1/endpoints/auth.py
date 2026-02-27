"""
Authentication endpoints: register, login, refresh, change-password, Google OAuth2
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

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

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_tokens(user: User) -> TokenResponse:
    access_token  = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user,
    )


def _ensure_cart(user: User, db: Session) -> None:
    """Create an empty cart for the user if one doesn't exist."""
    if not db.query(Cart).filter(Cart.user_id == user.id).first():
        db.add(Cart(user_id=user.id))
        db.commit()


# ── Register ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Register a new customer account and return JWT tokens."""
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


# ── Login ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Login with email and password."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is disabled")
    return _make_tokens(user)


# ── Refresh Token ────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Get new access+refresh tokens using a valid refresh token."""
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
    """Change the authenticated user's password."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"message": "Password changed successfully"}


# ── Get Current User ──────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user info."""
    return current_user


# ── Google OAuth2 ─────────────────────────────────────────────────────────────

@router.post("/oauth/google", response_model=TokenResponse)
def google_oauth(payload: OAuthGoogleRequest, db: Session = Depends(get_db)):
    """
    Authenticate via Google OAuth2.

    Flow:
      1. Frontend loads Google Sign-In (gsi/client) and gets an ID token
      2. Frontend sends: POST /auth/oauth/google  { "id_token": "eyJ..." }
      3. Backend verifies token with Google and returns our JWT tokens

    Test in Postman:
      - Get a real Google ID token from: https://developers.google.com/identity/gsi/web/tools/explore
      - Or use the mock mode: send  { "id_token": "mock_test_token" }  while DEBUG=true
    """
    google_user = _verify_google_token(payload.id_token)

    # Find or create user
    is_new = False
    user = db.query(User).filter(User.email == google_user["email"]).first()

    if not user:
        is_new = True
        user = User(
            full_name=payload.full_name or google_user.get("name", google_user["email"].split("@")[0]),
            email=google_user["email"],
            phone=payload.phone,
            hashed_password=get_password_hash(google_user["sub"]),  # unusable hash
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
        # Update profile image if changed
        if google_user.get("picture") and user.profile_image != google_user["picture"]:
            user.profile_image = google_user["picture"]
            db.commit()
            db.refresh(user)

    tokens = _make_tokens(user)
    tokens.is_new_user = is_new
    return tokens


def _verify_google_token(id_token: str) -> dict:
    """
    Verify a Google ID token.
    - In production: uses google-auth library to verify properly.
    - In dev/test (DEBUG=true): accepts 'mock_test_token' and returns fake user data.
    """
    from app.core.config import settings

    # ── Mock mode for local testing ──────────────────────────────────────
    if settings.DEBUG and id_token in ("mock_test_token", "test"):
        return {
            "sub": "google_test_user_12345",
            "email": "oauth.test@gmail.com",
            "name": "OAuth Test User",
            "picture": "https://lh3.googleusercontent.com/test",
            "email_verified": True,
        }

    # ── Production: verify with Google ───────────────────────────────────
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
