"""
Razorpay payment utility
"""
import razorpay
import hmac
import hashlib
from app.core.config import settings


def get_razorpay_client() -> razorpay.Client:
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


def create_razorpay_order(amount_inr: float, order_number: str, currency: str = "INR") -> dict:
    """Create Razorpay order. amount_inr is in rupees; Razorpay needs paise."""
    client = get_razorpay_client()
    data = {
        "amount": int(amount_inr * 100),   # convert to paise
        "currency": currency,
        "receipt": order_number,
        "payment_capture": 1,
    }
    return client.order.create(data=data)


def verify_razorpay_signature(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> bool:
    """Verify Razorpay payment signature for security."""
    message = f"{razorpay_order_id}|{razorpay_payment_id}"
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, razorpay_signature)


def initiate_refund(razorpay_payment_id: str, amount_inr: float) -> dict:
    """Initiate a refund on a captured payment."""
    client = get_razorpay_client()
    return client.payment.refund(
        razorpay_payment_id,
        {"amount": int(amount_inr * 100)},
    )
