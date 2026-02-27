from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.schemas.product import ProductListResponse


class CartItemAdd(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int = 1


class CartItemUpdate(BaseModel):
    quantity: int


class CartItemResponse(BaseModel):
    id: int
    product_id: int
    variant_id: Optional[int]
    quantity: int
    save_for_later: bool
    product: ProductListResponse

    class Config:
        from_attributes = True


class CartResponse(BaseModel):
    id: int
    items: List[CartItemResponse]
    coupon_code: Optional[str] = None
    subtotal: float
    discount_amount: float
    shipping_cost: float
    tax_amount: float
    total_amount: float

    class Config:
        from_attributes = True


class ApplyCouponRequest(BaseModel):
    coupon_code: str
