"""
Coupon endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.dependencies import get_db, get_current_user, require_admin
from app.models.user import User
from app.models.coupon import Coupon
from app.enums import DiscountType
from app.schemas.coupon import (
    CouponCreate, CouponUpdate, CouponResponse,
    CouponValidateRequest, CouponValidateResponse,
)
from app.services.coupon_service import coupon_service, CouponValidationError

router = APIRouter()


@router.post("/validate", response_model=CouponValidateResponse)
def validate_coupon(
    payload: CouponValidateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Validate a coupon at cart/checkout preview time.
    Returns discount amount if valid; returns valid=False with a precise
    error message on the FIRST rule that fails.
    Does NOT increment usage — that only happens after payment confirmation.
    """
    try:
        result = coupon_service.validate_coupon(
            db,
            code=payload.code,
            user_id=current_user.id,
            cart_subtotal=payload.order_amount,
        )
        return CouponValidateResponse(
            valid=True,
            discount_amount=result.discount_amount,
            message="Coupon applied successfully.",
            coupon=result.coupon,
        )
    except CouponValidationError as exc:
        return CouponValidateResponse(
            valid=False,
            discount_amount=0.0,
            message=exc.message,
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
    # Req #6: Reject percentage coupons > 100% at creation time
    if payload.discount_type == DiscountType.percentage and payload.discount_value > 100:
        raise HTTPException(
            status_code=422,
            detail="Percentage discount cannot exceed 100%.",
        )

    exists = db.query(Coupon).filter(Coupon.code == payload.code.upper()).first()
    if exists:
        raise HTTPException(status_code=400, detail="Coupon code already exists.")

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
        raise HTTPException(status_code=404, detail="Coupon not found.")

    update_data = payload.model_dump(exclude_none=True)

    # Req #6: Prevent updating a percentage coupon to > 100%
    new_type  = update_data.get("discount_type", coupon.discount_type)
    new_value = update_data.get("discount_value", coupon.discount_value)
    if new_type == DiscountType.percentage and new_value > 100:
        raise HTTPException(
            status_code=422,
            detail="Percentage discount cannot exceed 100%.",
        )

    for field, value in update_data.items():
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
        raise HTTPException(status_code=404, detail="Coupon not found.")
    db.delete(coupon)
    db.commit()
