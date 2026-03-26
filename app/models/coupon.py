"""
Coupon model

Enum source: app.enums.DiscountType  (do not redefine locally)
DB column:   String (VARCHAR) — no PostgreSQL native enum type.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from app.enums import DiscountType  # noqa: F401 — re-exported for import compatibility


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(300), nullable=True)
    discount_type = Column(String(15), nullable=False)
    discount_value = Column(Float, nullable=False)
    min_order_value = Column(Float, default=0.0)
    max_discount_amount = Column(Float, nullable=True)  # cap for percentage coupons
    usage_limit = Column(Integer, nullable=True)        # max total uses
    usage_per_user = Column(Integer, default=1)
    used_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    usage_records = relationship("CouponUsage", back_populates="coupon", cascade="all, delete-orphan")
