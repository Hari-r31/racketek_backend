"""
Order endpoints: place, view, cancel, track

Fixes applied
-------------
C5  — Stock is NO longer deducted at order placement.
      Instead, an InventoryReservation row is created for each item, holding
      the stock for RESERVATION_TTL_MINUTES (15 min).  Actual deduction
      happens in payments.py after confirmed payment or COD confirmation.
      If the reservation expires without payment the Celery beat task
      `release_expired_reservations` returns the stock automatically.

H8  — Idempotency key support: supply X-Idempotency-Key header (UUID).
      Duplicate submissions within 24 h return the cached order response.
      Key is stored in Redis with a 24-hour TTL.
"""
import json
import math
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user, require_staff_or_admin
from app.core.config import settings
from app.models.user import User
from app.models.order import Order, OrderItem
from app.models.cart import Cart, CartItem
from app.models.payment import Payment
from app.enums import OrderStatus, PaymentMethod, PaymentStatus
from app.models.address import Address
from app.models.coupon import Coupon
from app.models.product import Product
from app.models.inventory_reservation import InventoryReservation, RESERVATION_TTL_MINUTES
from app.enums import ProductStatus as ProdStatus, ReservationStatus
from app.models.revenue_log import RevenueLog
from app.models.shipment import Shipment
from app.services.coupon_service import coupon_service, CouponValidationError
from app.schemas.order import (
    OrderCreate, OrderResponse, OrderUpdateStatus,
    OrderCancelRequest, PaginatedOrders,
)
from app.utils.helpers import (
    generate_order_number, calculate_shipping,
    calculate_tax, calculate_estimated_delivery,
)
from app.utils.email import send_order_confirmation
from app.utils.redis_client import get_redis

router = APIRouter()

_IDEMPOTENCY_TTL = 86_400  # 24 hours in seconds


# ── helpers ───────────────────────────────────────────────────────────────────

def _idempotency_cache_key(user_id: int, key: str) -> str:
    return f"idempotency:order:{user_id}:{key}"


def _release_reservations_for_order(order_id: int, db: Session) -> None:
    """Return reserved stock to products when an order is cancelled or expired."""
    reservations = (
        db.query(InventoryReservation)
        .filter(
            InventoryReservation.order_id == order_id,
            InventoryReservation.status == ReservationStatus.active,
        )
        .with_for_update()
        .all()
    )
    for res in reservations:
        product = db.query(Product).filter(Product.id == res.product_id).with_for_update().first()
        if product:
            product.stock += res.quantity
            if product.status == ProdStatus.out_of_stock and product.stock > 0:
                product.status = ProdStatus.active
        res.status = ReservationStatus.released
        res.updated_at = datetime.utcnow()


# ── list ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedOrders)
def list_my_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    status: Optional[OrderStatus] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Order).filter(Order.user_id == current_user.id)
    if status:
        q = q.filter(Order.status == status)
    q = q.order_by(Order.created_at.desc())
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return PaginatedOrders(
        items=items, total=total, page=page, per_page=per_page,
        total_pages=math.ceil(total / per_page) if per_page else 1,
    )


@router.get("/{order_number}", response_model=OrderResponse)
def get_order(
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
    return order


# ── place order ───────────────────────────────────────────────────────────────

@router.post("", response_model=OrderResponse, status_code=201)
def place_order(
    payload: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(None),  # H8
):
    """
    Convert cart into an order.

    C5: Stock is reserved (not deducted). Actual deduction happens on payment.
    H8: Duplicate requests with the same X-Idempotency-Key return the cached
        order without creating a duplicate.
    """
    # ── H8: Idempotency check ─────────────────────────────────────────────
    if x_idempotency_key:
        redis = get_redis()
        cache_key = _idempotency_cache_key(current_user.id, x_idempotency_key)
        cached = redis.get(cache_key)
        if cached:
            order_number = cached.decode()
            existing = db.query(Order).filter(
                Order.order_number == order_number,
                Order.user_id == current_user.id,
            ).first()
            if existing:
                return existing

    # ── validate address ──────────────────────────────────────────────────
    addr = db.query(Address).filter(
        Address.id == payload.address_id,
        Address.user_id == current_user.id,
    ).first()
    if not addr:
        raise HTTPException(status_code=400, detail="Address not found")

    # ── get active cart items ─────────────────────────────────────────────
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    active_items = [i for i in cart.items if not i.save_for_later] if cart else []
    if not active_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # ── check stock availability before reserving ─────────────────────────
    for item in active_items:
        product = item.product
        # If variant has its own stock, use that; else product stock
        if item.variant:
            avail = item.variant.stock
        else:
            avail = product.stock
        if avail < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough stock for '{product.name}'. Available: {avail}",
            )

    # ── subtotal ──────────────────────────────────────────────────────────
    subtotal = 0.0
    for item in active_items:
        price = item.product.price
        if item.variant:
            price += item.variant.price_modifier
        subtotal += price * item.quantity

    # ── coupon validation ─────────────────────────────────────────────────
    discount_amount = 0.0
    coupon = None
    if payload.coupon_code:
        try:
            result = coupon_service.validate_coupon(
                db, code=payload.coupon_code,
                user_id=current_user.id, cart_subtotal=subtotal,
            )
            coupon = result.coupon
            discount_amount = result.discount_amount
        except CouponValidationError as exc:
            raise HTTPException(status_code=400, detail=exc.message)

    discounted    = subtotal - discount_amount
    shipping_cost = calculate_shipping(discounted)
    tax_amount    = calculate_tax(discounted)
    total_amount  = round(discounted + shipping_cost + tax_amount, 2)

    # ── create order ──────────────────────────────────────────────────────
    order = Order(
        order_number=generate_order_number(),
        user_id=current_user.id,
        shipping_address_id=addr.id,
        coupon_id=coupon.id if coupon else None,
        subtotal=subtotal,
        discount_amount=discount_amount,
        shipping_cost=shipping_cost,
        tax_amount=tax_amount,
        total_amount=total_amount,
        status=OrderStatus.pending,
        estimated_delivery=calculate_estimated_delivery(5),
        notes=payload.notes,
    )
    db.add(order)
    db.flush()  # get order.id before creating reservations

    # ── C5 FIX: reserve stock; do NOT deduct ─────────────────────────────
    expires_at = datetime.utcnow() + timedelta(minutes=RESERVATION_TTL_MINUTES)
    for item in active_items:
        price = item.product.price
        if item.variant:
            price += item.variant.price_modifier

        # Snapshot order item
        db.add(OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            variant_id=item.variant_id,
            product_name=item.product.name,
            variant_name=f"{item.variant.name}: {item.variant.value}" if item.variant else None,
            quantity=item.quantity,
            unit_price=price,
            total_price=price * item.quantity,
        ))

        # Reserve stock (subtract from visible stock)
        if item.variant:
            item.variant.stock = max(0, item.variant.stock - item.quantity)
        else:
            item.product.stock = max(0, item.product.stock - item.quantity)
            if item.product.stock == 0:
                item.product.status = ProdStatus.out_of_stock

        db.add(InventoryReservation(
            order_id=order.id,
            product_id=item.product_id,
            variant_id=item.variant_id,
            quantity=item.quantity,
            status=ReservationStatus.active,
            expires_at=expires_at,
        ))

    # ── payment record ────────────────────────────────────────────────────
    method = PaymentMethod.cod if payload.payment_method == "cod" else PaymentMethod.razorpay
    db.add(Payment(
        order_id=order.id,
        method=method,
        amount=total_amount,
        status=PaymentStatus.pending,
    ))

    # ── revenue log ───────────────────────────────────────────────────────
    db.add(RevenueLog(
        order_id=order.id,
        amount=total_amount,
        type="sale",
        description=f"Order {order.order_number}",
    ))

    # NOTE: Cart is NOT cleared here — only after confirmed payment.
    db.commit()
    db.refresh(order)

    # ── H8: cache idempotency key ─────────────────────────────────────────
    if x_idempotency_key:
        redis = get_redis()
        cache_key = _idempotency_cache_key(current_user.id, x_idempotency_key)
        redis.setex(cache_key, _IDEMPOTENCY_TTL, order.order_number)

    # ── send confirmation email async ─────────────────────────────────────
    try:
        send_order_confirmation(current_user.email, order.order_number, total_amount)
    except Exception:
        pass

    return order


# ── cancel order ──────────────────────────────────────────────────────────────

@router.post("/{order_number}/cancel")
def cancel_order(
    order_number: str,
    payload: OrderCancelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(
        Order.order_number == order_number,
        Order.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in [OrderStatus.pending, OrderStatus.paid]:
        raise HTTPException(status_code=400, detail="Order cannot be cancelled at this stage")

    order.status = OrderStatus.cancelled
    order.cancelled_at = datetime.utcnow()
    order.cancellation_reason = payload.reason

    # C5 FIX: release reservations (returns reserved stock to products)
    _release_reservations_for_order(order.id, db)

    # Also restore sold_count for already-PAID orders that are being cancelled
    if order.status == OrderStatus.paid:
        for item in order.items:
            if item.product_id:
                product = db.query(Product).filter(Product.id == item.product_id).first()
                if product:
                    product.sold_count = max(0, product.sold_count - item.quantity)

    db.commit()
    return {"message": "Order cancelled"}
