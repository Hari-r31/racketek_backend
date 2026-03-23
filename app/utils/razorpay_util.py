"""
Razorpay payment utility

M4 FIX: Client is created as a module-level singleton and reused across
         requests. Previously a new Client() was instantiated on every call.
"""
import razorpay
import hmac
import hashlib
from app.core.config import settings


# M4 FIX: singleton — one instance for the lifetime of the process
_razorpay_client: razorpay.Client | None = None


def get_razorpay_client() -> razorpay.Client:
    global _razorpay_client
    if _razorpay_client is None:
        _razorpay_client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
    return _razorpay_client


def create_razorpay_order(amount_inr: float, order_number: str, currency: str = "INR") -> dict:
    """Create Razorpay order. amount_inr is in rupees; Razorpay needs paise."""
    data = {
        "amount": int(amount_inr * 100),
        "currency": currency,
        "receipt": order_number,
        "payment_capture": 1,
    }
    return get_razorpay_client().order.create(data=data)


def verify_razorpay_signature(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> bool:
    """Verify Razorpay payment signature."""
    message = f"{razorpay_order_id}|{razorpay_payment_id}"
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, razorpay_signature)


def initiate_refund(razorpay_payment_id: str, amount_inr: float) -> dict:
    """Initiate a refund on a captured payment."""
    return get_razorpay_client().payment.refund(
        razorpay_payment_id,
        {"amount": int(amount_inr * 100)},
    )
