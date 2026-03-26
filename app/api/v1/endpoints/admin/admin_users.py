"""
Admin user management

H1 FIX: Replaced `payload: dict = Body(...)` with a strict Pydantic schema
         (AdminUserUpdate) that only allows role and is_active to be updated.
         Eliminates mass-assignment risk on the User model.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import math

from app.core.dependencies import get_db, require_admin
from app.models.user import User
from app.enums import UserRole
from app.schemas.user import UserResponse

router = APIRouter()


# H1 FIX: strict schema — only these two fields are permitted
class AdminUserUpdate(BaseModel):
    role:      Optional[UserRole] = None
    is_active: Optional[bool]     = None


@router.get("")
def admin_list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(User)
    if search:
        q = q.filter(
            User.email.ilike(f"%{search}%") | User.full_name.ilike(f"%{search}%")
        )
    if role:
        q = q.filter(User.role == role)
    if is_active is not None:
        q = q.filter(User.is_active == is_active)
    q = q.order_by(User.created_at.desc())
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [UserResponse.model_validate(u) for u in items],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": math.ceil(total / per_page) if per_page else 1,
    }


@router.put("/{user_id}")
def update_user(
    user_id: int,
    payload: AdminUserUpdate,          # H1 FIX: typed schema, not raw dict
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update user role and/or active status."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.patch("/{user_id}/block")
def block_user(
    user_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = not user.is_active
    db.commit()
    return {"is_active": user.is_active}


@router.patch("/{user_id}/role")
def update_role(
    user_id: int,
    role: UserRole,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = role
    db.commit()
    return {"role": role}
