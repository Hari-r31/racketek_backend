"""
Celery application setup
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
    beat_schedule={
        "send-low-stock-alerts-daily": {
            "task": "app.workers.order_tasks.send_low_stock_alerts",
            "schedule": 86400,  # every 24h
        },
    },
)
