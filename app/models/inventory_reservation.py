"""
InventoryReservation model

C5 FIX: Stock is no longer deducted at order placement.
Instead, a reservation holds the stock for RESERVATION_TTL_MINUTES (15 min)
while the user completes payment. The actual deduction happens only after
confirmed payment or COD confirmation.

A Celery beat task (`release_expired_reservations`) runs every minute to
release reservations whose expiry has passed and return stock to products.

States:
  ACTIVE    — stock is being held; payment in progress
  CONFIRMED — payment confirmed; stock permanently deducted (reservation retained for audit)
  RELEASED  — reservation expired or was cancelled; stock returned
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.db.base_class import Base

RESERVATION_TTL_MINUTES = 15


class ReservationStatus(str, enum.Enum):
    ACTIVE    = "active"
    CONFIRMED = "confirmed"
    RELEASED  = "released"


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"

    id         = Column(Integer, primary_key=True, index=True)
    order_id   = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    quantity   = Column(Integer, nullable=False)
    status     = Column(SAEnum(ReservationStatus), default=ReservationStatus.ACTIVE, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order   = relationship("Order",   foreign_keys=[order_id])
    product = relationship("Product", foreign_keys=[product_id])
