"""
Coupon schemas
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.coupon import DiscountType


class CouponCreate(BaseModel):
    code: str
    description: Optional[str] = None
    discount_type: DiscountType
    discount_value: float
    min_order_value: float = 0.0
    max_discount_amount: Optional[float] = None
    usage_limit: Optional[int] = None
    usage_per_user: int = 1
    is_active: bool = True
    expires_at: Optional[datetime] = None


class CouponUpdate(BaseModel):
    description: Optional[str] = None
    discount_value: Optional[float] = None
    min_order_value: Optional[float] = None
    max_discount_amount: Optional[float] = None
    usage_limit: Optional[int] = None
    usage_per_user: Optional[int] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None


class CouponResponse(BaseModel):
    id: int
    code: str
    description: Optional[str]
    discount_type: DiscountType
    discount_value: float
    min_order_value: float
    max_discount_amount: Optional[float]
    usage_limit: Optional[int]
    usage_per_user: int
    used_count: int
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class CouponValidateRequest(BaseModel):
    code: str
    order_amount: float


class CouponValidateResponse(BaseModel):
    valid: bool
    discount_amount: float
    message: str
    coupon: Optional[CouponResponse] = None
