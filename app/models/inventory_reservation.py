"""
InventoryReservation model

Enum source: app.enums.ReservationStatus  (do not redefine locally)
DB column:   String (VARCHAR) — no PostgreSQL native enum type.

C5 FIX: Stock is no longer deducted at order placement.
Instead, a reservation holds the stock for RESERVATION_TTL_MINUTES (15 min)
while the user completes payment. The actual deduction happens only after
confirmed payment or COD confirmation.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from app.enums import ReservationStatus  # noqa: F401 — re-exported for import compatibility

RESERVATION_TTL_MINUTES = 15


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"

    id         = Column(Integer, primary_key=True, index=True)
    order_id   = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    quantity   = Column(Integer, nullable=False)
    status     = Column(String(15), default=ReservationStatus.active, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order   = relationship("Order",   foreign_keys=[order_id])
    product = relationship("Product", foreign_keys=[product_id])
