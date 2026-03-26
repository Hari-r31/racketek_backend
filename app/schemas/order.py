"""
Order schemas
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.enums import OrderStatus


class OrderItemCreate(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int


class OrderCreate(BaseModel):
    address_id: int
    coupon_code: Optional[str] = None
    notes: Optional[str] = None
    payment_method: str = "razorpay"  # "razorpay" | "cod"


class OrderItemResponse(BaseModel):
    id: int
    product_id: Optional[int]
    variant_id: Optional[int]
    product_name: str
    variant_name: Optional[str]
    quantity: int
    unit_price: float
    total_price: float

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    id: int
    order_number: str
    status: OrderStatus
    subtotal: float
    discount_amount: float
    shipping_cost: float
    tax_amount: float
    total_amount: float
    notes: Optional[str]
    estimated_delivery: Optional[datetime]
    delivered_at: Optional[datetime]
    awb_number: Optional[str] = None
    tracking_url: Optional[str] = None
    items: List[OrderItemResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class OrderUpdateStatus(BaseModel):
    status: OrderStatus
    notes: Optional[str] = None


class OrderCancelRequest(BaseModel):
    reason: str


class PaginatedOrders(BaseModel):
    items: List[OrderResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
