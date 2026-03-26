"""
Coupon schemas
Backward-compatible — all existing fields preserved.

Enum source: app.enums.DiscountType  (do not redefine locally)
"""
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List
from datetime import datetime
from app.enums import DiscountType


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

    @model_validator(mode="after")
    def validate_discount_value(self) -> "CouponCreate":
        if self.discount_type == DiscountType.percentage and self.discount_value > 100:
            raise ValueError("Percentage discount cannot exceed 100%.")
        if self.discount_value <= 0:
            raise ValueError("Discount value must be greater than zero.")
        return self


class CouponUpdate(BaseModel):
    description: Optional[str] = None
    discount_type: Optional[DiscountType] = None
    discount_value: Optional[float] = None
    min_order_value: Optional[float] = None
    max_discount_amount: Optional[float] = None
    usage_limit: Optional[int] = None
    usage_per_user: Optional[int] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_percentage_on_update(self) -> "CouponUpdate":
        if (
            self.discount_type == DiscountType.percentage
            and self.discount_value is not None
            and self.discount_value > 100
        ):
            raise ValueError("Percentage discount cannot exceed 100%.")
        return self


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
    product_ids: Optional[List[int]] = None

    @field_validator("order_amount")
    @classmethod
    def amount_must_be_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("order_amount must be non-negative.")
        return v


class CouponValidateResponse(BaseModel):
    valid: bool
    discount_amount: float
    message: str
    coupon: Optional[CouponResponse] = None
