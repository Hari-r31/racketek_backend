"""
Utility helpers: slug generation, order number, pagination etc.
"""
import re
import uuid
import math
from datetime import datetime


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text


def generate_order_number() -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    unique = str(uuid.uuid4()).replace("-", "")[:6].upper()
    return f"RO-{timestamp}-{unique}"


def paginate(query, page: int, per_page: int):
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = math.ceil(total / per_page) if per_page else 1
    return items, total, total_pages


def calculate_shipping(order_total: float) -> float:
    """Simple shipping logic: free above ₹999, else ₹99."""
    if order_total >= 999:
        return 0.0
    return 99.0


def calculate_tax(amount: float, rate: float = 0.18) -> float:
    """GST 18% by default."""
    return round(amount * rate, 2)


def calculate_estimated_delivery(days: int = 5) -> datetime:
    from datetime import timedelta
    return datetime.utcnow() + timedelta(days=days)
