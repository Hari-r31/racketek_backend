"""
Async email tasks via Celery
"""
from app.workers.celery_app import celery_app
from app.utils.email import send_email, send_order_confirmation, send_order_status_update


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


@celery_app.task
def task_send_abandoned_cart_email(to_email: str, user_name: str, cart_items: list):
    html = f"""
    <h2>Hey {user_name}, you left something behind!</h2>
    <p>You have {len(cart_items)} item(s) in your cart at Racketek Outlet.</p>
    <p>Complete your purchase before items run out of stock.</p>
    <a href="https://racketek.com/cart" style="background:#e11d48;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;">
        Complete Purchase
    </a>
    """
    send_email(to_email, "Complete your Racketek purchase!", html)
