"""
InventoryReservation model

C5 FIX: Stock is no longer deducted at order placement.
Instead, a reservation holds the stock for RESERVATION_TTL_MINUTES (15 min)
while the user completes payment. The actual deduction happens only after
confirmed payment or COD confirmation.

ENUM FIX: status uses String (VARCHAR) — no PostgreSQL native enum type.
          create_type=False workaround is no longer needed.
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
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
    status     = Column(String(15), default=ReservationStatus.ACTIVE.value, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order   = relationship("Order",   foreign_keys=[order_id])
    product = relationship("Product", foreign_keys=[product_id])
