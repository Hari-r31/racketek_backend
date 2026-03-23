"""
Order / inventory background tasks

Fixes applied
-------------
C5  — release_expired_reservations(): runs every 60 s (beat schedule).
       Finds ACTIVE reservations whose expires_at has passed, returns stock
       to products, marks reservations RELEASED, and cancels the parent order
       if it is still PENDING (unpaid).
H5  — process_abandoned_carts(): respects email_marketing_consent flag,
       enforces 7-day cooldown via last_abandoned_cart_email_at column,
       and only fires for users who have opted in.
M7  — send_low_stock_alerts(): uses settings.SMTP_USER (already correct),
       but email body now uses settings.FRONTEND_URL for any links.
"""
import logging
from datetime import datetime, timedelta

from app.workers.celery_app import celery_app
from app.utils.email import send_email
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task
def release_expired_reservations():
    """
    C5 FIX: Release inventory reservations whose TTL has expired.

    For each expired ACTIVE reservation:
      1. Return quantity to product.stock.
      2. Re-activate product if it was marked OUT_OF_STOCK.
      3. Mark reservation as RELEASED.
      4. If the parent order is still PENDING, mark it CANCELLED.

    Runs every 60 seconds via Celery beat schedule.
    """
    from app.db.session import SessionLocal
    from app.models.inventory_reservation import InventoryReservation, ReservationStatus
    from app.models.order import Order, OrderStatus
    from app.models.product import Product, ProductStatus

    db = SessionLocal()
    released_count = 0
    cancelled_count = 0

    try:
        now = datetime.utcnow()
        expired = (
            db.query(InventoryReservation)
            .filter(
                InventoryReservation.status == ReservationStatus.ACTIVE,
                InventoryReservation.expires_at <= now,
            )
            .with_for_update(skip_locked=True)
            .all()
        )

        affected_order_ids = set()
        for res in expired:
            # Return stock
            product = db.query(Product).filter(
                Product.id == res.product_id
            ).with_for_update().first()
            if product:
                product.stock += res.quantity
                if product.status == ProductStatus.OUT_OF_STOCK and product.stock > 0:
                    product.status = ProductStatus.ACTIVE

            res.status = ReservationStatus.RELEASED
            res.updated_at = now
            affected_order_ids.add(res.order_id)
            released_count += 1

        # Cancel PENDING orders whose reservations all expired
        for order_id in affected_order_ids:
            order = db.query(Order).filter(
                Order.id == order_id,
                Order.status == OrderStatus.PENDING,
            ).first()
            if order:
                order.status = OrderStatus.CANCELLED
                order.cancelled_at = now
                order.cancellation_reason = "Payment not completed within 15 minutes"
                cancelled_count += 1

        db.commit()
        msg = f"Released {released_count} reservations, cancelled {cancelled_count} orders"
        logger.info("[release_expired_reservations] %s", msg)
        return msg

    except Exception as exc:
        db.rollback()
        logger.error("[release_expired_reservations] Error: %s", exc)
        raise
    finally:
        db.close()


@celery_app.task
def send_low_stock_alerts():
    """Send email to admin if products are low on stock."""
    from app.db.session import SessionLocal
    from app.models.product import Product

    db = SessionLocal()
    try:
        low = db.query(Product).filter(
            Product.stock <= Product.low_stock_threshold,
            Product.stock > 0,
        ).all()
        if not low:
            return "No low stock products"

        rows = "".join(
            f"<tr><td>{p.id}</td><td>{p.name}</td><td>{p.stock}</td><td>{p.low_stock_threshold}</td></tr>"
            for p in low
        )
        html = f"""
        <h2>Low Stock Alert – Racketek Outlet</h2>
        <table border='1' cellpadding='6'>
            <tr><th>ID</th><th>Product</th><th>Stock</th><th>Threshold</th></tr>
            {rows}
        </table>
        """
        send_email(settings.SMTP_USER, "⚠️ Low Stock Alert – Racketek", html)
        return f"Alert sent for {len(low)} products"
    finally:
        db.close()


@celery_app.task
def process_abandoned_carts():
    """
    H5 FIX: Check carts abandoned for >24 h and trigger abandoned-cart emails.

    Guards enforced BEFORE enqueuing:
      1. email_marketing_consent must be True on the User row.
      2. 7-day cooldown: last_abandoned_cart_email_at must be NULL or >7 days ago.
         (This column is added by migration; defaults to NULL for existing users.)
      3. Cart must have active (non-saved) items.
    """
    from app.db.session import SessionLocal
    from app.models.cart import Cart
    from app.workers.email_tasks import task_send_abandoned_cart_email

    db = SessionLocal()
    try:
        cutoff      = datetime.utcnow() - timedelta(hours=24)
        cooldown    = datetime.utcnow() - timedelta(days=7)

        carts = db.query(Cart).filter(Cart.updated_at <= cutoff).all()
        triggered = 0

        for cart in carts:
            if not cart.items or not cart.user:
                continue

            user = cart.user

            # H5 FIX: consent check
            if not getattr(user, "email_marketing_consent", False):
                continue

            # H5 FIX: cooldown check
            last_sent = getattr(user, "last_abandoned_cart_email_at", None)
            if last_sent and last_sent > cooldown:
                continue

            active_items = [
                {"name": i.product.name, "qty": i.quantity}
                for i in cart.items
                if not i.save_for_later and i.product
            ]
            if not active_items:
                continue

            task_send_abandoned_cart_email.delay(
                user.email,
                user.full_name,
                active_items,
            )

            # Update cooldown timestamp
            user.last_abandoned_cart_email_at = datetime.utcnow()
            triggered += 1

        db.commit()
        return f"Triggered {triggered} abandoned cart emails"
    finally:
        db.close()
