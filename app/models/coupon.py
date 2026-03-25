"""
Coupon model
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class DiscountType(str, enum.Enum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(300), nullable=True)
    discount_type = Column(SAEnum(DiscountType, values_callable=lambda x: [e.value for e in x]), nullable=False)
    discount_value = Column(Float, nullable=False)
    min_order_value = Column(Float, default=0.0)
    max_discount_amount = Column(Float, nullable=True)  # cap for percentage coupons
    usage_limit = Column(Integer, nullable=True)        # max total uses
    usage_per_user = Column(Integer, default=1)
    used_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Back-ref to per-user usage records (added in migration 008)
    usage_records = relationship("CouponUsage", back_populates="coupon", cascade="all, delete-orphan")
