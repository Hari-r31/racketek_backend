"""
Async email tasks via Celery

M7 FIX: Removed hardcoded "https://racketek.com/cart" URL.
         Now uses settings.FRONTEND_URL everywhere.
H5 FIX: task_send_abandoned_cart_email is now a no-op placeholder.
         The actual abandoned-cart logic has moved into order_tasks.py
         process_abandoned_carts() which enforces the consent flag and cooldown.
"""
from app.workers.celery_app import celery_app
from app.utils.email import send_email, send_order_confirmation, send_order_status_update
from app.core.config import settings


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def task_send_order_confirmation(self, to_email: str, order_number: str, total: float):
    try:
        send_order_confirmation(to_email, order_number, total)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def task_send_order_status_update(self, to_email: str, order_number: str, status: str):
    try:
        send_order_status_update(to_email, order_number, status)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def task_send_abandoned_cart_email(self, to_email: str, user_name: str, cart_items: list):
    """
    H5 FIX: Consent and cooldown are enforced by process_abandoned_carts()
    before this task is enqueued. This task only handles the actual send.

    M7 FIX: Cart URL built from settings.FRONTEND_URL — no hardcoded domain.
    """
    cart_url = f"{settings.FRONTEND_URL}/cart"
    html = f"""
    <h2>Hey {user_name}, you left something behind!</h2>
    <p>You have {len(cart_items)} item(s) in your cart at Racketek Outlet.</p>
    <p>Complete your purchase before items run out of stock.</p>
    <a href="{cart_url}"
       style="background:#e11d48;color:white;padding:12px 24px;
              text-decoration:none;border-radius:6px;display:inline-block;margin-top:12px">
        Complete Purchase
    </a>
    <p style="margin-top:24px;font-size:12px;color:#888">
        You're receiving this email because you opted in to cart reminders.<br>
        <a href="{settings.FRONTEND_URL}/account/notifications">Manage email preferences</a>
    </p>
    """
    try:
        send_email(to_email, "Complete your Racketek purchase!", html)
    except Exception as exc:
        raise self.retry(exc=exc)
