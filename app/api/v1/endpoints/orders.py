"""
Order endpoints: place, view, cancel, track
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import math

from app.core.dependencies import get_db, get_current_user, require_staff_or_admin
from app.models.user import User
from app.models.order import Order, OrderItem, OrderStatus
from app.models.cart import Cart, CartItem
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.address import Address
from app.models.coupon import Coupon, DiscountType
from app.models.revenue_log import RevenueLog
from app.models.shipment import Shipment
from app.schemas.order import OrderCreate, OrderResponse, OrderUpdateStatus, OrderCancelRequest, PaginatedOrders
from app.utils.helpers import (
    generate_order_number, calculate_shipping,
    calculate_tax, calculate_estimated_delivery,
)
from app.utils.email import send_order_confirmation

router = APIRouter()


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


@router.post("", response_model=OrderResponse, status_code=201)
def place_order(
    payload: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Convert cart into an order."""
    # Validate address
    addr = db.query(Address).filter(
        Address.id == payload.address_id,
        Address.user_id == current_user.id,
    ).first()
    if not addr:
        raise HTTPException(status_code=400, detail="Address not found")

    # Get cart
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    active_items = [i for i in cart.items if not i.save_for_later] if cart else []
    if not active_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Subtotal
    subtotal = 0.0
    for item in active_items:
        price = item.product.price
        if item.variant:
            price += item.variant.price_modifier
        subtotal += price * item.quantity

    # Coupon
    discount_amount = 0.0
    coupon = None
    if payload.coupon_code:
        coupon = db.query(Coupon).filter(
            Coupon.code == payload.coupon_code.upper(),
            Coupon.is_active == True,
        ).first()
        if coupon:
            if coupon.discount_type == DiscountType.PERCENTAGE:
                discount_amount = subtotal * (coupon.discount_value / 100)
                if coupon.max_discount_amount:
                    discount_amount = min(discount_amount, coupon.max_discount_amount)
            else:
                discount_amount = coupon.discount_value
            coupon.used_count += 1

    discounted = subtotal - discount_amount
    shipping_cost = calculate_shipping(discounted)
    tax_amount = calculate_tax(discounted)
    total_amount = round(discounted + shipping_cost + tax_amount, 2)

    # Create order
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
        status=OrderStatus.PENDING,
        estimated_delivery=calculate_estimated_delivery(5),
        notes=payload.notes,
    )
    db.add(order)
    db.flush()

    # Create order items + deduct stock
    for item in active_items:
        price = item.product.price
        if item.variant:
            price += item.variant.price_modifier
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
        item.product.stock = max(0, item.product.stock - item.quantity)
        item.product.sold_count += item.quantity

    # Payment record
    method = PaymentMethod.COD if payload.payment_method == "cod" else PaymentMethod.RAZORPAY
    payment = Payment(
        order_id=order.id,
        method=method,
        amount=total_amount,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)

    # Revenue log
    db.add(RevenueLog(
        order_id=order.id,
        amount=total_amount,
        type="sale",
        description=f"Order {order.order_number}",
    ))

    # Clear cart items
    for item in active_items:
        db.delete(item)
    cart.coupon_id = None

    db.commit()
    db.refresh(order)

    # Send confirmation email async (fire and forget)
    try:
        send_order_confirmation(current_user.email, order.order_number, total_amount)
    except Exception:
        pass

    return order


@router.post("/{order_number}/cancel")
def cancel_order(
    order_number: str,
    payload: OrderCancelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import datetime
    order = db.query(Order).filter(
        Order.order_number == order_number,
        Order.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in [OrderStatus.PENDING, OrderStatus.PAID]:
        raise HTTPException(status_code=400, detail="Order cannot be cancelled at this stage")

    order.status = OrderStatus.CANCELLED
    order.cancelled_at = datetime.utcnow()
    order.cancellation_reason = payload.reason
    db.commit()
    return {"message": "Order cancelled"}
