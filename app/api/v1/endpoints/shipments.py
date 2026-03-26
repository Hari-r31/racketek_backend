"""
Shipment tracking endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.dependencies import get_db, get_current_user, require_staff_or_admin
from app.models.user import User
from app.models.order import Order
from app.models.shipment import Shipment
from app.enums import OrderStatus, ShipmentStatus
from app.schemas.shipment import ShipmentCreate, ShipmentUpdate, ShipmentResponse

router = APIRouter()


@router.get("/{order_number}", response_model=ShipmentResponse)
def track_shipment(
    order_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(
        Order.order_number == order_number,
        Order.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if not order.shipment:
        raise HTTPException(status_code=404, detail="Shipment not yet created")
    return order.shipment


@router.post("", response_model=ShipmentResponse, status_code=201)
def create_shipment(
    payload: ShipmentCreate,
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == payload.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    shipment = Shipment(
        order_id=order.id,
        tracking_number=payload.tracking_number,
        carrier=payload.carrier,
        carrier_tracking_url=payload.carrier_tracking_url,
        estimated_delivery=payload.estimated_delivery,
        shipped_at=datetime.utcnow(),
    )
    db.add(shipment)
    order.status = OrderStatus.shipped
    db.commit()
    db.refresh(shipment)
    return shipment


@router.put("/{shipment_id}", response_model=ShipmentResponse)
def update_shipment(
    shipment_id: int,
    payload: ShipmentUpdate,
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(shipment, field, value)

    if payload.status == ShipmentStatus.delivered:
        shipment.delivered_at = datetime.utcnow()
        if shipment.order:
            shipment.order.status = OrderStatus.delivered
            shipment.order.delivered_at = datetime.utcnow()

    db.commit()
    db.refresh(shipment)
    return shipment
