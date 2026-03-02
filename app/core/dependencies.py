"""
FastAPI dependency injections: DB session, current user, role checks
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.security import decode_token
from app.models.user import User, UserRole

# auto_error=False → returns None instead of 403 when no Bearer header is present.
# This lets our handler return a proper 401, which the frontend interceptor can catch
# and use to refresh tokens. With auto_error=True FastAPI raises 403 which the
# frontend never retries.
bearer_scheme = HTTPBearer(auto_error=False)


def get_db():
    """Yield a database session and close it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # No Authorization header at all
    if credentials is None:
        raise credentials_exception

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None or payload.get("type") != "access":
        raise credentials_exception

    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id), User.is_active == True).first()
    if user is None:
        raise credentials_exception

    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def require_staff_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.STAFF]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff or Admin privileges required",
        )
    return current_user
