"""
CouponService
=============
Single source of truth for all coupon validation and usage-increment logic.

Design principles
-----------------
* Fail fast – reject on the FIRST failed rule and return a precise message.
* Validate-only at cart/order-preview time; never mutate usage there.
* Increment usage ONLY inside increment_usage(), which must be called
  after confirmed payment inside an open DB transaction.
* Row-level locking (SELECT ... FOR UPDATE) prevents race conditions when
  multiple concurrent requests try to redeem the same coupon.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.coupon import Coupon, DiscountType
from app.models.coupon_usage import CouponUsage


# ---------------------------------------------------------------------------
# Result / Error types
# ---------------------------------------------------------------------------

class CouponValidationError(Exception):
    """Raised by validate_coupon on the first rule that fails."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class CouponValidationResult:
    coupon: Coupon
    discount_amount: float          # already capped and rounded


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class CouponService:
    """Stateless service – instantiate per request or use the module-level singleton."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_coupon(
        self,
        db: Session,
        *,
        code: str,
        user_id: int,
        cart_subtotal: float,
        product_ids: Optional[List[int]] = None,
    ) -> CouponValidationResult:
        """
        Validate a coupon code against all business rules IN ORDER.
        Raises CouponValidationError on the first failure.
        Does NOT modify any database state.

        Parameters
        ----------
        db            : Active SQLAlchemy session.
        code          : Raw coupon code entered by the user (case-insensitive).
        user_id       : ID of the user attempting to apply the coupon.
        cart_subtotal : Pre-discount cart total (sum of item prices × quantities).
        product_ids   : Optional list of product IDs in the cart for scope checks.

        Returns
        -------
        CouponValidationResult with the matched Coupon and the computed discount.
        """
        code = code.strip().upper()

        # ── Rule 1: Coupon exists ────────────────────────────────────────
        coupon: Optional[Coupon] = (
            db.query(Coupon).filter(Coupon.code == code).first()
        )
        if not coupon:
            raise CouponValidationError("Coupon code does not exist.")

        # ── Rule 2: Coupon is active ─────────────────────────────────────
        if not coupon.is_active:
            raise CouponValidationError("This coupon is no longer active.")

        # ── Rule 3: Not expired ──────────────────────────────────────────
        if coupon.expires_at and coupon.expires_at < datetime.utcnow():
            raise CouponValidationError("This coupon has expired.")

        # ── Rule 4: Global usage < usage_limit ──────────────────────────
        if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
            raise CouponValidationError("This coupon's usage limit has been reached.")

        # ── Rule 5: Per-user usage < usage_per_user ──────────────────────
        user_use_count: int = (
            db.query(CouponUsage)
            .filter(
                CouponUsage.coupon_id == coupon.id,
                CouponUsage.user_id == user_id,
            )
            .count()
        )
        if user_use_count >= coupon.usage_per_user:
            raise CouponValidationError(
                f"You have already used this coupon "
                f"{user_use_count} time(s). "
                f"Maximum {coupon.usage_per_user} use(s) per user allowed."
            )

        # ── Rule 6: Cart subtotal >= min_order_value ─────────────────────
        if cart_subtotal < coupon.min_order_value:
            raise CouponValidationError(
                f"This coupon requires a minimum order value of "
                f"₹{coupon.min_order_value:.2f}. "
                f"Your cart total is ₹{cart_subtotal:.2f}."
            )

        # ── Rule 7: Product eligibility (extensible hook) ────────────────
        # The current schema is not product-scoped, but this is the correct
        # place to add scope validation when that feature is added.
        # Example future check:
        #   if coupon.applicable_product_ids:
        #       if not any(pid in coupon.applicable_product_ids for pid in product_ids or []):
        #           raise CouponValidationError("Coupon not valid for items in your cart.")

        # ── Discount calculation ─────────────────────────────────────────
        discount_amount = self._calculate_discount(coupon, cart_subtotal)

        return CouponValidationResult(
            coupon=coupon,
            discount_amount=discount_amount,
        )

    def increment_usage(
        self,
        db: Session,
        *,
        coupon_id: int,
        user_id: int,
        order_id: int,
    ) -> None:
        """
        Atomically increment coupon usage after confirmed payment.

        MUST be called inside an active transaction (i.e., before db.commit()).
        Uses SELECT FOR UPDATE to lock the coupon row and prevent concurrent
        double-redemption under high load.

        Raises CouponValidationError if limits are somehow exceeded between
        validation-time and payment-time (edge case guard).
        """
        # Lock the coupon row for the duration of this transaction
        coupon: Optional[Coupon] = (
            db.query(Coupon)
            .filter(Coupon.id == coupon_id)
            .with_for_update()
            .first()
        )
        if not coupon:
            # Coupon was deleted after the order was placed — skip silently.
            return

        # Double-check global limit under lock
        if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
            raise CouponValidationError(
                "Coupon usage limit was reached by a concurrent request. "
                "Please choose a different coupon."
            )

        # Double-check per-user limit under lock
        user_use_count: int = (
            db.query(CouponUsage)
            .filter(
                CouponUsage.coupon_id == coupon_id,
                CouponUsage.user_id == user_id,
            )
            .count()
        )
        if user_use_count >= coupon.usage_per_user:
            raise CouponValidationError(
                "Per-user coupon limit was reached by a concurrent request. "
                "Please choose a different coupon."
            )

        # Safe to increment
        coupon.used_count += 1
        db.add(
            CouponUsage(
                coupon_id=coupon_id,
                user_id=user_id,
                order_id=order_id,
                used_at=datetime.utcnow(),
            )
        )
        # Caller is responsible for db.commit()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _calculate_discount(self, coupon: Coupon, subtotal: float) -> float:
        """
        Compute the final discount amount.

        Safety guards:
        * Percentage coupons: value must be ≤ 100 (req #6).
        * Fixed coupons: discount is capped at the cart subtotal (req #7).
        """
        if coupon.discount_type == DiscountType.PERCENTAGE:
            # Req #6: Reject bad coupon data defensively
            pct = min(coupon.discount_value, 100.0)
            discount = subtotal * (pct / 100.0)
            if coupon.max_discount_amount:
                discount = min(discount, coupon.max_discount_amount)
        else:
            # Req #7: Fixed discount cannot exceed cart subtotal
            discount = min(coupon.discount_value, subtotal)

        return round(discount, 2)


# ---------------------------------------------------------------------------
# Module-level singleton (import and use directly)
# ---------------------------------------------------------------------------
coupon_service = CouponService()
