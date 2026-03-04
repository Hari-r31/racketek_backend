"""
CouponUsage model – tracks per-user coupon redemptions.
Created alongside the existing Coupon model without altering its schema.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class CouponUsage(Base):
    __tablename__ = "coupon_usage"

    id = Column(Integer, primary_key=True, index=True)
    coupon_id = Column(
        Integer,
        ForeignKey("coupons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,          # Req #5
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,          # Req #5
    )
    order_id = Column(
        Integer,
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    used_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships (back-refs kept optional to avoid circular imports)
    coupon = relationship("Coupon", back_populates="usage_records")
    user   = relationship("User")
    order  = relationship("Order")

    __table_args__ = (
        # Allows multiple uses per user up to usage_per_user; enforce count in service.
        Index("ix_coupon_usage_coupon_user", "coupon_id", "user_id"),
    )
