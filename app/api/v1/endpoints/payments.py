"""
Payment endpoints – Razorpay + COD

Fixes applied
-------------
C5  — Stock is now CONFIRMED (sold_count updated) only after successful payment.
      InventoryReservation rows are marked CONFIRMED, not re-deducted.
C6  — POST /payments/razorpay/webhook: server-to-server authoritative confirmation
      from Razorpay. Idempotent: duplicate webhook events are safely ignored.
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user, require_admin
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentStatus
from app.models.cart import Cart, CartItem
from app.models.inventory_reservation import InventoryReservation, ReservationStatus
from app.schemas.payment import (
    RazorpayOrderCreate, RazorpayOrderResponse,
    PaymentVerify, CODConfirm, RefundRequest, PaymentResponse,
)
from app.utils.razorpay_util import (
    create_razorpay_order, verify_razorpay_signature, initiate_refund,
)
from app.utils.email import send_order_status_update
from app.core.config import settings
from app.services.coupon_service import coupon_service, CouponValidationError

logger = logging.getLogger(__name__)
router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────

def _clear_cart(user_id: int, db: Session) -> None:
    """Delete all non-saved cart items for the user after successful payment."""
    cart = db.query(Cart).filter(Cart.user_id == user_id).first()
    if cart:
        db.query(CartItem).filter(
            CartItem.cart_id == cart.id,
            CartItem.save_for_later == False,
        ).delete(synchronize_session=False)
        cart.coupon_id = None


def _confirm_reservations(order_id: int, db: Session) -> None:
    """
    C5 FIX: Mark all ACTIVE reservations as CONFIRMED and update sold_count.
    Stock was already subtracted at reservation time; this step just finalises it.
    """
    reservations = (
        db.query(InventoryReservation)
        .filter(
            InventoryReservation.order_id == order_id,
            InventoryReservation.status == ReservationStatus.ACTIVE,
        )
        .all()
    )
    for res in reservations:
        res.status = ReservationStatus.CONFIRMED
        res.updated_at = datetime.utcnow()
        # Update sold_count on the product
        if res.product:
            res.product.sold_count += res.quantity


def _mark_order_paid(
    order: Order,
    payment: Payment,
    user_id: int,
    db: Session,
    razorpay_payment_id: str = None,
    razorpay_signature: str = None,
) -> None:
    """Shared logic for marking an order as paid after any confirmation path."""
    if payment.razorpay_payment_id:
        # idempotency: already processed
        return

    if razorpay_payment_id:
        payment.razorpay_payment_id = razorpay_payment_id
    if razorpay_signature:
        payment.razorpay_signature = razorpay_signature
    payment.status = PaymentStatus.SUCCESS
    payment.paid_at = datetime.utcnow()

    order.status = OrderStatus.PAID

    # C5 FIX: confirm reservations (finalise stock deduction)
    _confirm_reservations(order.id, db)

    # Increment coupon usage only after confirmed payment
    if order.coupon_id:
        try:
            coupon_service.increment_usage(
                db,
                coupon_id=order.coupon_id,
                user_id=user_id,
                order_id=order.id,
            )
        except CouponValidationError as exc:
            logger.warning(
                "Coupon increment skipped for order %s: %s",
                order.order_number, exc.message,
            )

    _clear_cart(user_id, db)


# ── Create Razorpay order ─────────────────────────────────────────────────────

@router.post("/razorpay/create-order", response_model=RazorpayOrderResponse)
def create_razorpay_payment_order(
    payload: RazorpayOrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Step 1: Create a Razorpay order. Return razorpay_order_id to frontend."""
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
        amount=rz_order["amount"],
        currency=rz_order["currency"],
        key_id=settings.RAZORPAY_KEY_ID,
    )


# ── Verify Razorpay payment (client-side callback) ────────────────────────────

@router.post("/razorpay/verify")
def verify_razorpay_payment(
    payload: PaymentVerify,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Step 2: Verify Razorpay HMAC signature and mark order as paid.
    This is the fast UX path triggered by the frontend after Razorpay checkout.
    The webhook (below) is the authoritative fallback.
    """
    order = db.query(Order).filter(
        Order.id == payload.order_id,
        Order.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Idempotency: already paid (possibly via webhook)
    if order.status == OrderStatus.PAID:
        return {"message": "Payment already confirmed.", "order_number": order.order_number}

    if not verify_razorpay_signature(
        payload.razorpay_order_id,
        payload.razorpay_payment_id,
        payload.razorpay_signature,
    ):
        raise HTTPException(status_code=400, detail="Payment signature verification failed")

    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    _mark_order_paid(
        order, payment, current_user.id, db,
        razorpay_payment_id=payload.razorpay_payment_id,
        razorpay_signature=payload.razorpay_signature,
    )
    db.commit()

    try:
        send_order_status_update(current_user.email, order.order_number, "paid")
    except Exception:
        pass

    return {"message": "Payment verified. Order confirmed.", "order_number": order.order_number}


# ── C6 FIX: Razorpay webhook ──────────────────────────────────────────────────

@router.post("/razorpay/webhook")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_razorpay_signature: str = Header(None),
):
    """
    C6 FIX: Server-to-server authoritative payment confirmation from Razorpay.

    Security:
      - Verifies X-Razorpay-Signature against raw request body using
        the RAZORPAY_WEBHOOK_SECRET (set in Razorpay Dashboard → Webhooks).
      - Falls back gracefully if RAZORPAY_WEBHOOK_SECRET is not configured
        (logs a warning — you should configure it in production).

    Idempotency:
      - If the order is already PAID, returns 200 immediately (safe replay).
      - Razorpay retries webhooks on non-2xx responses, so we must always
        return 200 for valid events, even if the order is already processed.

    Supported events:
      - payment.captured  — mark order paid
      - payment.failed    — mark payment failed
    """
    raw_body = await request.body()

    # Verify webhook signature
    if settings.RAZORPAY_WEBHOOK_SECRET:
        if not x_razorpay_signature:
            logger.warning("[Webhook] Missing X-Razorpay-Signature header")
            raise HTTPException(status_code=400, detail="Missing webhook signature")

        expected = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, x_razorpay_signature):
            logger.warning("[Webhook] Invalid signature — possible spoofed request")
            raise HTTPException(status_code=400, detail="Invalid webhook signature")
    else:
        logger.warning(
            "[Webhook] RAZORPAY_WEBHOOK_SECRET not configured — skipping signature check. "
            "Set this in .env for production security."
        )

    try:
        event = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = event.get("event")
    payload    = event.get("payload", {})

    # ── payment.captured ─────────────────────────────────────────────────
    if event_type == "payment.captured":
        rz_payment = payload.get("payment", {}).get("entity", {})
        razorpay_order_id  = rz_payment.get("order_id")
        razorpay_payment_id = rz_payment.get("id")

        if not razorpay_order_id:
            return {"status": "ignored", "reason": "no order_id in payload"}

        payment = (
            db.query(Payment)
            .filter(Payment.razorpay_order_id == razorpay_order_id)
            .first()
        )
        if not payment:
            logger.warning("[Webhook] No payment found for razorpay_order_id=%s", razorpay_order_id)
            return {"status": "ignored", "reason": "order not found"}

        order = db.query(Order).filter(Order.id == payment.order_id).first()
        if not order:
            return {"status": "ignored", "reason": "order not found"}

        if order.status == OrderStatus.PAID:
            logger.info("[Webhook] Order %s already paid — idempotent replay", order.order_number)
            return {"status": "already_processed"}

        _mark_order_paid(
            order, payment, order.user_id, db,
            razorpay_payment_id=razorpay_payment_id,
        )
        db.commit()
        logger.info("[Webhook] Order %s marked PAID via webhook", order.order_number)

        try:
            if order.user:
                send_order_status_update(order.user.email, order.order_number, "paid")
        except Exception:
            pass

        return {"status": "ok"}

    # ── payment.failed ────────────────────────────────────────────────────
    elif event_type == "payment.failed":
        rz_payment = payload.get("payment", {}).get("entity", {})
        razorpay_order_id = rz_payment.get("order_id")

        if razorpay_order_id:
            payment = (
                db.query(Payment)
                .filter(Payment.razorpay_order_id == razorpay_order_id)
                .first()
            )
            if payment and payment.status == PaymentStatus.PENDING:
                payment.status = PaymentStatus.FAILED
                payment.failure_reason = rz_payment.get("error_description", "Payment failed")
                db.commit()
                logger.info("[Webhook] Payment marked FAILED for order_id=%s", razorpay_order_id)

        return {"status": "ok"}

    # ── unhandled event ───────────────────────────────────────────────────
    else:
        logger.debug("[Webhook] Unhandled event type: %s", event_type)
        return {"status": "ignored", "event": event_type}


# ── COD confirm ───────────────────────────────────────────────────────────────

@router.post("/cod/confirm")
def confirm_cod(
    payload: CODConfirm,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirm a Cash-on-Delivery order."""
    order = db.query(Order).filter(
        Order.id == payload.order_id,
        Order.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status != OrderStatus.PENDING:
        raise HTTPException(status_code=400, detail="Order is not in pending state")

    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    order.status = OrderStatus.PROCESSING

    # C5 FIX: confirm reservations on COD too
    _confirm_reservations(order.id, db)

    if order.coupon_id:
        try:
            coupon_service.increment_usage(
                db,
                coupon_id=order.coupon_id,
                user_id=current_user.id,
                order_id=order.id,
            )
        except CouponValidationError as exc:
            logger.warning(
                "Coupon increment skipped for COD order %s: %s",
                order.order_number, exc.message,
            )

    _clear_cart(current_user.id, db)
    db.commit()
    return {"message": "COD order confirmed.", "order_number": order.order_number}


# ── Refund ────────────────────────────────────────────────────────────────────

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


# ── Get payment ───────────────────────────────────────────────────────────────

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
