"""
Celery application setup

M6 FIX:
  - task_acks_late=True  — tasks are acknowledged AFTER completion, not on receipt.
    If a worker crashes mid-task the broker re-queues it automatically.
  - task_reject_on_worker_lost=True — ensures the above works on unclean crashes.
  - worker_prefetch_multiplier=1 — prevents a single worker from hoarding tasks.
  - Sentry integration is wired in if SENTRY_DSN is set (see main.py for SDK init).
"""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "racketek",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.email_tasks",
        "app.workers.order_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,

    # M6 FIX: reliability settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Result expiry — keep results for 24 h then clean up
    result_expires=86400,

    beat_schedule={
        "send-low-stock-alerts-daily": {
            "task": "app.workers.order_tasks.send_low_stock_alerts",
            "schedule": 86400,  # every 24 h
        },
        # C5 FIX: release expired inventory reservations every minute
        "release-expired-reservations": {
            "task": "app.workers.order_tasks.release_expired_reservations",
            "schedule": 60,  # every 60 s
        },
    },
)

# M6 FIX: hook Celery into Sentry if DSN is configured
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            integrations=[CeleryIntegration()],
        )
    except ImportError:
        pass
