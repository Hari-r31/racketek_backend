"""
Payment schemas – Razorpay + COD
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.enums import PaymentMethod, PaymentStatus


class RazorpayOrderCreate(BaseModel):
    order_id: int  # our internal order id


class RazorpayOrderResponse(BaseModel):
    razorpay_order_id: str
    amount: int          # in paise
    currency: str
    key_id: str          # public key to send to frontend


class PaymentVerify(BaseModel):
    order_id: int
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class CODConfirm(BaseModel):
    order_id: int


class RefundRequest(BaseModel):
    order_id: int
    amount: Optional[float] = None   # None = full refund
    reason: str


class PaymentResponse(BaseModel):
    id: int
    order_id: int
    method: PaymentMethod
    status: PaymentStatus
    amount: float
    currency: str
    razorpay_order_id: Optional[str]
    razorpay_payment_id: Optional[str]
    refund_amount: Optional[float]
    paid_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
