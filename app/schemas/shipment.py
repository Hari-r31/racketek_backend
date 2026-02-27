"""
Shipment schemas
"""
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from app.models.shipment import ShipmentStatus


class ShipmentCreate(BaseModel):
    order_id: int
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None
    carrier_tracking_url: Optional[str] = None
    estimated_delivery: Optional[datetime] = None


class ShipmentUpdate(BaseModel):
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None
    carrier_tracking_url: Optional[str] = None
    status: Optional[ShipmentStatus] = None
    estimated_delivery: Optional[datetime] = None
    tracking_events: Optional[List[Any]] = None


class ShipmentResponse(BaseModel):
    id: int
    order_id: int
    tracking_number: Optional[str]
    carrier: Optional[str]
    carrier_tracking_url: Optional[str]
    status: ShipmentStatus
    shipped_at: Optional[datetime]
    estimated_delivery: Optional[datetime]
    delivered_at: Optional[datetime]
    tracking_events: List[Any]
    created_at: datetime

    class Config:
        from_attributes = True
