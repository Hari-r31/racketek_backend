"""
Shipment / Delivery Tracking model

Enum source: app.enums.ShipmentStatus  (do not redefine locally)
DB column:   String (VARCHAR) — no PostgreSQL native enum type.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from app.enums import ShipmentStatus  # noqa: F401 — re-exported for import compatibility


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False)
    tracking_number = Column(String(200), unique=True, nullable=True, index=True)
    carrier = Column(String(100), nullable=True)
    carrier_tracking_url = Column(String(500), nullable=True)
    status = Column(String(30), default=ShipmentStatus.pending)
    shipped_at = Column(DateTime, nullable=True)
    estimated_delivery = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    # JSON list of tracking events: [{timestamp, location, status, description}]
    tracking_events = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order = relationship("Order", back_populates="shipment")
