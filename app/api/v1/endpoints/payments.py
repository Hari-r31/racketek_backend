"""
Payment endpoints – Razorpay + COD
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.dependencies import get_db, get_current_user, require_admin
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import (
    RazorpayOrderCreate, RazorpayOrderResponse,
    PaymentVerify, CODConfirm, RefundRequest, PaymentResponse,
)
from app.utils.razorpay_util import (
    create_razorpay_order, verify_razorpay_signature, initiate_refund
)
from app.utils.email import send_order_status_update
from app.core.config import settings

router = APIRouter()


@router.post("/razorpay/create-order", response_model=RazorpayOrderResponse)
def create_razorpay_payment_order(
    payload: RazorpayOrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Step 1: Create a Razorpay order. Return order_id to the frontend."""
    order = db.query(Order).filter(
        Order.id == payload.order_id,
        Order.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.PENDING:
        raise HTTPException(status_code=400, detail="Order is not in pending state")

    rz_order = create_razorpay_order(order.total_amount, order.order_number)

    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    if payment:
        payment.razorpay_order_id = rz_order["id"]
        db.commit()

    return RazorpayOrderResponse(
        razorpay_order_id=rz_order["id"],
        amount=rz_order["amount"],      # paise
        currency=rz_order["currency"],
        key_id=settings.RAZORPAY_KEY_ID,
    )


@router.post("/razorpay/verify")
def verify_razorpay_payment(
    payload: PaymentVerify,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Step 2: Verify Razorpay signature and mark order as paid."""
    order = db.query(Order).filter(
        Order.id == payload.order_id,
        Order.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    is_valid = verify_razorpay_signature(
        payload.razorpay_order_id,
        payload.razorpay_payment_id,
        payload.razorpay_signature,
    )
    if not is_valid:
        raise HTTPException(status_code=400, detail="Payment signature verification failed")

    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    payment.razorpay_payment_id = payload.razorpay_payment_id
    payment.razorpay_signature = payload.razorpay_signature
    payment.status = PaymentStatus.SUCCESS
    payment.paid_at = datetime.utcnow()

    order.status = OrderStatus.PAID
    db.commit()

    try:
        send_order_status_update(current_user.email, order.order_number, "paid")
    except Exception:
        pass

    return {"message": "Payment verified. Order confirmed.", "order_number": order.order_number}


@router.post("/cod/confirm")
def confirm_cod(
    payload: CODConfirm,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirm a Cash-on-Delivery order (no actual payment yet)."""
    order = db.query(Order).filter(
        Order.id == payload.order_id,
        Order.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    # For COD, payment is "pending" until delivery
    order.status = OrderStatus.PROCESSING
    db.commit()
    return {"message": "COD order confirmed.", "order_number": order.order_number}


@router.post("/refund")
def process_refund(
    payload: RefundRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin: initiate Razorpay refund."""
    order = db.query(Order).filter(Order.id == payload.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    if not payment or not payment.razorpay_payment_id:
        raise HTTPException(status_code=400, detail="No Razorpay payment found for this order")

    refund_amount = payload.amount or payment.amount
    refund = initiate_refund(payment.razorpay_payment_id, refund_amount)

    payment.status = PaymentStatus.REFUNDED
    payment.refund_amount = refund_amount
    payment.refund_reason = payload.reason
    payment.razorpay_refund_id = refund.get("id")
    payment.refunded_at = datetime.utcnow()
    order.status = OrderStatus.REFUNDED
    db.commit()
    return {"message": "Refund initiated", "refund_id": refund.get("id")}


@router.get("/{order_id}", response_model=PaymentResponse)
def get_payment(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(
        Order.id == order_id, Order.user_id == current_user.id
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    payment = db.query(Payment).filter(Payment.order_id == order_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment
