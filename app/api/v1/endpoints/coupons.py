"""
Coupon endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.core.dependencies import get_db, get_current_user, require_admin
from app.models.user import User
from app.models.coupon import Coupon, DiscountType
from app.schemas.coupon import (
    CouponCreate, CouponUpdate, CouponResponse,
    CouponValidateRequest, CouponValidateResponse,
)

router = APIRouter()


@router.post("/validate", response_model=CouponValidateResponse)
def validate_coupon(
    payload: CouponValidateRequest,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    coupon = db.query(Coupon).filter(
        Coupon.code == payload.code.upper(),
        Coupon.is_active == True,
    ).first()

    if not coupon:
        return CouponValidateResponse(valid=False, discount_amount=0.0, message="Invalid coupon code")
    if coupon.expires_at and coupon.expires_at < datetime.utcnow():
        return CouponValidateResponse(valid=False, discount_amount=0.0, message="Coupon has expired")
    if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
        return CouponValidateResponse(valid=False, discount_amount=0.0, message="Coupon usage limit reached")
    if payload.order_amount < coupon.min_order_value:
        return CouponValidateResponse(
            valid=False,
            discount_amount=0.0,
            message=f"Minimum order value is ₹{coupon.min_order_value}",
        )

    if coupon.discount_type == DiscountType.PERCENTAGE:
        discount = payload.order_amount * (coupon.discount_value / 100)
        if coupon.max_discount_amount:
            discount = min(discount, coupon.max_discount_amount)
    else:
        discount = coupon.discount_value

    return CouponValidateResponse(
        valid=True,
        discount_amount=round(discount, 2),
        message="Coupon applied successfully",
        coupon=coupon,
    )


@router.get("", response_model=List[CouponResponse])
def list_coupons(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(Coupon).order_by(Coupon.created_at.desc()).all()


@router.post("", response_model=CouponResponse, status_code=201)
def create_coupon(
    payload: CouponCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    exists = db.query(Coupon).filter(Coupon.code == payload.code.upper()).first()
    if exists:
        raise HTTPException(status_code=400, detail="Coupon code already exists")
    data = payload.model_dump()
    data["code"] = data["code"].upper()
    coupon = Coupon(**data)
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.put("/{coupon_id}", response_model=CouponResponse)
def update_coupon(
    coupon_id: int,
    payload: CouponUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(coupon, field, value)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.delete("/{coupon_id}", status_code=204)
def delete_coupon(
    coupon_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    db.delete(coupon)
    db.commit()
