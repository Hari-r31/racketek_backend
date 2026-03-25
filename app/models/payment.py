"""
Payment model - Razorpay integration
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum as SAEnum, Text
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class PaymentMethod(str, enum.Enum):
    RAZORPAY = "razorpay"
    COD = "cod"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False)
    method = Column(SAEnum(PaymentMethod, values_callable=lambda x: [e.value for e in x]), nullable=False)
    status = Column(SAEnum(PaymentStatus, values_callable=lambda x: [e.value for e in x]), default=PaymentStatus.PENDING)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR")

    # Razorpay specific fields
    razorpay_order_id = Column(String(200), nullable=True, index=True)
    razorpay_payment_id = Column(String(200), nullable=True, index=True)
    razorpay_signature = Column(String(500), nullable=True)
    razorpay_refund_id = Column(String(200), nullable=True)

    refund_amount = Column(Float, nullable=True)
    refund_reason = Column(Text, nullable=True)
    failure_reason = Column(String(500), nullable=True)

    paid_at = Column(DateTime, nullable=True)
    refunded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="payment")
