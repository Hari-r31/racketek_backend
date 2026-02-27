"""
Order / inventory background tasks
"""
from app.workers.celery_app import celery_app
from app.utils.email import send_email
from app.core.config import settings


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
    """Check carts that haven't been updated in 24h and trigger abandoned cart emails."""
    from app.db.session import SessionLocal
    from app.models.cart import Cart, CartItem
    from datetime import datetime, timedelta
    from app.workers.email_tasks import task_send_abandoned_cart_email

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        carts = db.query(Cart).filter(Cart.updated_at <= cutoff).all()
        triggered = 0
        for cart in carts:
            if not cart.items or not cart.user:
                continue
            items_summary = [
                {"name": i.product.name, "qty": i.quantity}
                for i in cart.items
                if not i.save_for_later and i.product
            ]
            if items_summary:
                task_send_abandoned_cart_email.delay(
                    cart.user.email,
                    cart.user.full_name,
                    items_summary,
                )
                triggered += 1
        return f"Triggered {triggered} abandoned cart emails"
    finally:
        db.close()
