"""
Return request endpoints — with stock restoration on completion
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.core.dependencies import get_db, get_current_user, require_staff_or_admin
from app.models.user import User
from app.models.order import Order
from app.models.product import Product, ProductVariant
from app.models.return_request import ReturnRequest
from app.enums import OrderStatus, ReturnStatus
from app.models.order import OrderItem
from app.schemas.return_request import ReturnCreate, ReturnAdminUpdate, ReturnResponse
from app.models.revenue_log import RevenueLog

router = APIRouter()

STOCK_RESTORE_ON = {ReturnStatus.completed, ReturnStatus.approved}


def _restore_stock_for_order(order: Order, db: Session):
    """Restore product/variant stock for all items in the order."""
    for item in order.items:
        if item.product_id:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                product.stock += item.quantity
                product.sold_count = max(0, product.sold_count - item.quantity)
        if item.variant_id:
            variant = db.query(ProductVariant).filter(ProductVariant.id == item.variant_id).first()
            if variant:
                variant.stock += item.quantity


# ── Customer endpoints ────────────────────────────────────────────────────────

@router.get("", response_model=List[ReturnResponse])
def my_returns(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(ReturnRequest).filter(ReturnRequest.user_id == current_user.id).all()


@router.post("", response_model=ReturnResponse, status_code=201)
def request_return(
    payload: ReturnCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(
        Order.id == payload.order_id,
        Order.user_id == current_user.id,
        Order.status == OrderStatus.delivered,
    ).first()
    if not order:
        raise HTTPException(status_code=400, detail="Order not found or not eligible for return")

    existing = db.query(ReturnRequest).filter(
        ReturnRequest.order_id == payload.order_id,
        ReturnRequest.user_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Return already requested for this order")

    rr = ReturnRequest(
        order_id=payload.order_id,
        user_id=current_user.id,
        reason=payload.reason,
    )
    db.add(rr)
    order.status = OrderStatus.returned
    db.commit()
    db.refresh(rr)
    return rr


# ── Admin endpoints ───────────────────────────────────────────────────────────

@router.get("/admin", response_model=List[ReturnResponse])
def admin_list_returns(
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    return db.query(ReturnRequest).order_by(ReturnRequest.created_at.desc()).all()


@router.put("/admin/{return_id}", response_model=ReturnResponse)
def admin_update_return(
    return_id: int,
    payload: ReturnAdminUpdate,
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    rr = db.query(ReturnRequest).filter(ReturnRequest.id == return_id).first()
    if not rr:
        raise HTTPException(status_code=404, detail="Return request not found")

    old_status = rr.status
    new_status = payload.status if payload.status else old_status

    # Restore stock exactly once: when transitioning to COMPLETED or APPROVED
    if new_status in STOCK_RESTORE_ON and old_status not in STOCK_RESTORE_ON:
        order = db.query(Order).filter(Order.id == rr.order_id).first()
        if order:
            _restore_stock_for_order(order, db)

            # Log refund in revenue_log
            if payload.refund_amount or rr.refund_amount:
                refund_amt = payload.refund_amount or rr.refund_amount
                db.add(RevenueLog(
                    order_id=order.id,
                    amount=-abs(refund_amt),
                    type="refund",
                    description=f"Return #{rr.id} approved — ₹{refund_amt} refunded",
                ))

            # Mark order as REFUNDED once refund is initiated
            if new_status == ReturnStatus.completed:
                order.status = OrderStatus.refunded

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(rr, field, value)

    rr.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(rr)
    return rr
