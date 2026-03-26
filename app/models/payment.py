"""
Payment model - Razorpay integration

Enum source: app.enums.PaymentMethod, app.enums.PaymentStatus  (do not redefine locally)
DB column:   String (VARCHAR) — no PostgreSQL native enum types.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from app.enums import PaymentMethod, PaymentStatus  # noqa: F401 — re-exported for import compatibility


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False)
    method = Column(String(20), nullable=False)
    status = Column(String(30), default=PaymentStatus.pending)
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
