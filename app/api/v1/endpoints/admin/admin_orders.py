"""
Admin order management — full lifecycle with courier tracking
BUG 4 FIX: When admin saves shipment details, also copy awb_number + tracking_url
           onto the Order row so customers can see it directly.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import asc, desc, func
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

def _norm(val):
    return val.value if hasattr(val, "value") else val

# ── Statuses that mean stock should be restored ───────────────────────────────
# Use plain string values so comparison works whether status is enum or plain string from DB
STOCK_RESTORE_STATUSES = {"cancelled", "returned", "refunded"}


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
# Sortable column map
_SORT_COLUMNS = {
    "created_at":    Order.created_at,
    "total_amount":  Order.total_amount,
    "order_number":  Order.order_number,
    "status":        Order.status,
}


@router.get("")
def admin_list_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,          # accept raw string — compare case-insensitively
    search: Optional[str] = None,
    sort: Optional[str] = None,            # e.g. "created_at_desc" / "customer_name_asc"
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    from app.models.user import User as UserModel  # local import to avoid circular

    q = (
        db.query(Order)
        .options(
            joinedload(Order.user),
            joinedload(Order.items),
            joinedload(Order.shipping_address),
        )
    )

    # Status filter — use func.lower() so it matches both "PENDING" and "pending" in DB
    if status and status.strip():
        normalised = status.strip().lower()
        q = q.filter(func.lower(Order.status) == normalised)

    if search:
        q = q.filter(Order.order_number.ilike(f"%{search}%"))

    # Sorting
    sort_col = Order.created_at
    sort_dir = desc
    if sort:
        # Format: "<field>_asc" or "<field>_desc"
        # Field name itself may contain underscores so split on last "_asc"/"_desc"
        if sort.endswith("_asc"):
            field_key = sort[:-4]
            sort_dir = asc
        elif sort.endswith("_desc"):
            field_key = sort[:-5]
            sort_dir = desc
        else:
            field_key = sort

        # customer_name sort — join users and sort by full_name
        if field_key == "customer_name":
            q = q.join(UserModel, Order.user_id == UserModel.id, isouter=True)
            sort_col = UserModel.full_name
        elif field_key in _SORT_COLUMNS:
            sort_col = _SORT_COLUMNS[field_key]

    q = q.order_by(sort_dir(sort_col))

    total = q.count()
    orders = q.offset((page - 1) * per_page).limit(per_page).all()

    # Serialise to dicts so user / items nested data is included
    def _order_dict(o: Order):
        return {
            "id":              o.id,
            "order_number":    o.order_number,
            "status": _norm(o.status),
            "subtotal":        o.subtotal,
            "discount_amount": o.discount_amount,
            "shipping_cost":   o.shipping_cost,
            "tax_amount":      o.tax_amount,
            "total_amount":    o.total_amount,
            "notes":           o.notes,
            "estimated_delivery": o.estimated_delivery.isoformat() if o.estimated_delivery else None,
            "delivered_at":    o.delivered_at.isoformat() if o.delivered_at else None,
            "awb_number":      o.awb_number,
            "tracking_url":    o.tracking_url,
            "created_at":      o.created_at.isoformat() if o.created_at else None,
            "user": {
                "id":        o.user.id,
                "full_name": o.user.full_name,
                "email":     o.user.email,
                "phone":     getattr(o.user, "phone", None),
            } if o.user else None,
            "shipping_address": {
                "full_name":      getattr(o.shipping_address, "full_name", None),
                "address_line1":  getattr(o.shipping_address, "address_line1", None),
                "address_line2":  getattr(o.shipping_address, "address_line2", None),
                "city":           getattr(o.shipping_address, "city", None),
                "state":          getattr(o.shipping_address, "state", None),
                "pincode":        getattr(o.shipping_address, "pincode", None),
                "phone":          getattr(o.shipping_address, "phone", None),
            } if o.shipping_address else None,
            "items": [
                {
                    "id":           item.id,
                    "product_id":   item.product_id,
                    "variant_id":   item.variant_id,
                    "product_name": item.product_name,
                    "variant_name": item.variant_name,
                    "quantity":     item.quantity,
                    "unit_price":   item.unit_price,
                    "total_price":  item.total_price,
                }
                for item in o.items
            ],
        }

    return {
        "items":       [_order_dict(o) for o in orders],
        "total":       total,
        "page":        page,
        "per_page":    per_page,
        "total_pages": math.ceil(total / per_page) if per_page else 1,
    }


@router.get("/{order_id}")
def admin_get_order(
    order_id: int,
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .options(
            joinedload(Order.user),
            joinedload(Order.items),
            joinedload(Order.shipping_address),
            joinedload(Order.shipment),
        )
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Return a fully serialised dict so nested relationships are included
    return {
        "id":              order.id,
        "order_number":    order.order_number,
        "status": _norm(order.status),
        "subtotal":        order.subtotal,
        "discount_amount": order.discount_amount,
        "shipping_cost":   order.shipping_cost,
        "tax_amount":      order.tax_amount,
        "total_amount":    order.total_amount,
        "notes":           order.notes,
        "estimated_delivery": order.estimated_delivery.isoformat() if order.estimated_delivery else None,
        "delivered_at":    order.delivered_at.isoformat() if order.delivered_at else None,
        "cancelled_at":    order.cancelled_at.isoformat() if order.cancelled_at else None,
        "awb_number":      order.awb_number,
        "tracking_url":    order.tracking_url,
        "created_at":      order.created_at.isoformat() if order.created_at else None,
        "user": {
            "id":        order.user.id,
            "full_name": order.user.full_name,
            "email":     order.user.email,
            "phone":     getattr(order.user, "phone", None),
        } if order.user else None,
        "shipping_address": {
            "full_name":      getattr(order.shipping_address, "full_name", None),
            "address_line1":  getattr(order.shipping_address, "address_line1", None),
            "address_line2":  getattr(order.shipping_address, "address_line2", None),
            "city":           getattr(order.shipping_address, "city", None),
            "state":          getattr(order.shipping_address, "state", None),
            "pincode":        getattr(order.shipping_address, "pincode", None),
            "phone":          getattr(order.shipping_address, "phone", None),
        } if order.shipping_address else None,
        "items": [
            {
                "id":           item.id,
                "product_id":   item.product_id,
                "variant_id":   item.variant_id,
                "product_name": item.product_name,
                "variant_name": item.variant_name,
                "quantity":     item.quantity,
                "unit_price":   item.unit_price,
                "total_price":  item.total_price,
            }
            for item in order.items
        ],
    }


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

    # Normalise DB value — may be stored as "PENDING" (old) or "pending" (new)
    old_status_str = (order.status or "").lower()
    old_status = old_status_str
    new_status = _norm(payload.status).lower()

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

    order.status = new_status  # always write lowercase
    if payload.notes:
        order.notes = payload.notes
    if new_status == "delivered":
        order.delivered_at = datetime.utcnow()
    if new_status == "cancelled":
        order.cancelled_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    if order.user and order.user.email:
        try:
            send_order_status_update(order.user.email, order.order_number, new_status)
        except Exception:
            pass

    return {"id": order.id, "order_number": order.order_number, "status": order.status}


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
    if _norm(order.status) in ("paid", "processing"): 
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
        "status": _norm(shipment.status),
        "shipped_at": shipment.shipped_at,
        "estimated_delivery": shipment.estimated_delivery,
        "delivered_at": shipment.delivered_at,
        "events": events,
    }


def _get_delhivery_token() -> str:
    from app.core.config import settings
    return getattr(settings, "DELHIVERY_API_TOKEN", "")
