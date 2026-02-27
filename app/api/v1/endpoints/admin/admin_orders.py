"""
Admin order management
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
import math

from app.core.dependencies import get_db, require_staff_or_admin
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.schemas.order import OrderResponse, OrderUpdateStatus, PaginatedOrders
from app.utils.email import send_order_status_update

router = APIRouter()


@router.get("", response_model=PaginatedOrders)
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
    return PaginatedOrders(
        items=items, total=total, page=page, per_page=per_page,
        total_pages=math.ceil(total / per_page) if per_page else 1,
    )


@router.get("/{order_id}", response_model=OrderResponse)
def admin_get_order(
    order_id: int,
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: int,
    payload: OrderUpdateStatus,
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = payload.status
    if payload.notes:
        order.notes = payload.notes
    db.commit()
    db.refresh(order)

    # Notify customer
    if order.user and order.user.email:
        try:
            send_order_status_update(order.user.email, order.order_number, payload.status.value)
        except Exception:
            pass
    return order
