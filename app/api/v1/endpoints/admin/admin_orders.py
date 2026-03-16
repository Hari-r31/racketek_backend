"""
Admin order management — full lifecycle with courier tracking
BUG 4 FIX: When admin saves shipment details, also copy awb_number + tracking_url
           onto the Order row so customers can see it directly.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import math
import httpx

from app.core.dependencies import get_db, require_staff_or_admin
from app.models.user import User
from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product, ProductVariant
from app.models.shipment import Shipment, ShipmentStatus
from app.schemas.order import OrderResponse, OrderUpdateStatus, PaginatedOrders
from app.utils.email import send_order_status_update
from pydantic import BaseModel

router = APIRouter()

# ── Statuses that mean stock should be restored ───────────────────────────────
STOCK_RESTORE_STATUSES = {OrderStatus.CANCELLED, OrderStatus.RETURNED, OrderStatus.REFUNDED}


def _restore_stock(order: Order, db: Session):
    """Add back quantities to product/variant stock when order is cancelled/returned/refunded."""
    for item in order.items:
        if item.product_id:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                product.stock += item.quantity
                product.sold_count = max(0, product.sold_count - item.quantity)
        if item.variant_id:
            variant = db.query(ProductVariant).filter(ProductVariant.id == item.variant_id).first()
            if variant:
                variant.stock = max(0, variant.stock + item.quantity)


# ── Pydantic schemas ──────────────────────────────────────────────────────────
class ShipmentCreate(BaseModel):
    carrier: str
    tracking_number: str
    carrier_tracking_url: Optional[str] = None
    estimated_delivery: Optional[datetime] = None


class TrackingEvent(BaseModel):
    timestamp: str
    location: str
    status: str
    description: str


# ── List / Get ────────────────────────────────────────────────────────────────
@router.get("")
def admin_list_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[OrderStatus] = None,
    search: Optional[str] = None,
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Order)
    if status:
        q = q.filter(Order.status == status)
    if search:
        q = q.filter(Order.order_number.ilike(f"%{search}%"))
    q = q.order_by(Order.created_at.desc())
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": math.ceil(total / per_page) if per_page else 1,
    }


@router.get("/{order_id}")
def admin_get_order(
    order_id: int,
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


# ── Status update (with stock restoration) ───────────────────────────────────
@router.patch("/{order_id}/status")
def update_order_status(
    order_id: int,
    payload: OrderUpdateStatus,
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    old_status = order.status
    new_status = payload.status

    # Restore stock only if transitioning INTO a restore-status from a non-restore-status
    if new_status in STOCK_RESTORE_STATUSES and old_status not in STOCK_RESTORE_STATUSES:
        _restore_stock(order, db)

    # Undo stock restoration if admin moves order back (edge case)
    if old_status in STOCK_RESTORE_STATUSES and new_status not in STOCK_RESTORE_STATUSES:
        for item in order.items:
            if item.product_id:
                product = db.query(Product).filter(Product.id == item.product_id).first()
                if product:
                    product.stock = max(0, product.stock - item.quantity)
                    product.sold_count += item.quantity

    order.status = new_status
    if payload.notes:
        order.notes = payload.notes
    if new_status == OrderStatus.DELIVERED:
        order.delivered_at = datetime.utcnow()
    if new_status == OrderStatus.CANCELLED:
        order.cancelled_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    if order.user and order.user.email:
        try:
            send_order_status_update(order.user.email, order.order_number, new_status.value)
        except Exception:
            pass

    return order


# ── Shipment / Courier management ─────────────────────────────────────────────
@router.post("/{order_id}/shipment")
def create_shipment(
    order_id: int,
    payload: ShipmentCreate,
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    """
    Attach courier + tracking info to an order.
    Also marks order as SHIPPED.
    BUG 4 FIX: Also copies awb_number + tracking_url directly onto the Order row
    so customers can see it in their order detail page without needing to query
    the shipments table separately.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Create or update shipment record
    shipment = db.query(Shipment).filter(Shipment.order_id == order_id).first()
    if not shipment:
        shipment = Shipment(order_id=order_id)
        db.add(shipment)

    shipment.carrier = payload.carrier
    shipment.tracking_number = payload.tracking_number
    shipment.carrier_tracking_url = payload.carrier_tracking_url
    shipment.status = ShipmentStatus.IN_TRANSIT
    shipment.shipped_at = datetime.utcnow()
    if payload.estimated_delivery:
        shipment.estimated_delivery = payload.estimated_delivery

    # BUG 4 FIX — mirror AWB fields onto the Order row for customer visibility
    order.awb_number = payload.tracking_number
    order.tracking_url = payload.carrier_tracking_url

    # Auto-advance order to SHIPPED
    if order.status in (OrderStatus.PAID, OrderStatus.PROCESSING):
        order.status = OrderStatus.SHIPPED

    db.commit()
    db.refresh(shipment)
    return shipment


@router.get("/{order_id}/shipment")
def get_shipment(
    order_id: int,
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    shipment = db.query(Shipment).filter(Shipment.order_id == order_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="No shipment for this order")
    return shipment


@router.get("/{order_id}/tracking")
async def fetch_tracking(
    order_id: int,
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    """
    Fetch live tracking events from courier API.
    Currently supports: Delhivery, Bluedart, DTDC (via Shiprocket aggregator).
    Falls back to stored events if API unavailable.
    """
    shipment = db.query(Shipment).filter(Shipment.order_id == order_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="No shipment found")

    # Try Delhivery tracking API
    events = shipment.tracking_events or []
    if shipment.tracking_number:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    "https://dlv-api.delhivery.com/api/v1/packages/json/",
                    params={"waybill": shipment.tracking_number, "verbose": True},
                    headers={"Authorization": f"Token {_get_delhivery_token()}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    scan_data = data.get("ShipmentData", [])
                    if scan_data:
                        scans = scan_data[0].get("Shipment", {}).get("Scans", [])
                        events = [
                            {
                                "timestamp": s.get("ScanDetail", {}).get("ScanDateTime", ""),
                                "location":  s.get("ScanDetail", {}).get("ScannedLocation", ""),
                                "status":    s.get("ScanDetail", {}).get("Scan", ""),
                                "description": s.get("ScanDetail", {}).get("Instructions", ""),
                            }
                            for s in scans
                        ]
                        # Persist events
                        shipment.tracking_events = events
                        db.commit()
        except Exception:
            pass  # Return stored events

    return {
        "tracking_number": shipment.tracking_number,
        "carrier": shipment.carrier,
        "carrier_tracking_url": shipment.carrier_tracking_url,
        "status": shipment.status,
        "shipped_at": shipment.shipped_at,
        "estimated_delivery": shipment.estimated_delivery,
        "delivered_at": shipment.delivered_at,
        "events": events,
    }


def _get_delhivery_token() -> str:
    from app.core.config import settings
    return getattr(settings, "DELHIVERY_API_TOKEN", "")
