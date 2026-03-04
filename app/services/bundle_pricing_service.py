"""
BundlePricingService
====================
Single source of truth for Build Your Bundle discount logic.

Design principles:
* Completely isolated — zero coupling to Cart, Checkout, or Coupon code paths.
* Pure calculation: no DB access, no side effects.
* Instantiated once as a module-level singleton; import and call directly.

Formula:
    discountPercent = per_item_discount * selected_item_count
    cappedDiscount  = min(discountPercent, max_cap)
    finalPrice      = subtotal - (subtotal * cappedDiscount / 100)
"""
from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class BundlePriceBreakdown:
    subtotal:         float   # raw sum of (price × qty) for all selected items
    item_count:       int     # total units selected (sum of quantities)
    discount_percent: float   # capped discount percentage applied
    discount_amount:  float   # ₹ amount saved
    final_price:      float   # subtotal − discount_amount


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class BundlePricingService:
    """Stateless service for Build Your Bundle discount calculation."""

    def calculate(
        self,
        subtotal: float,
        selected_item_count: int,
        per_item_discount: float = 5.0,
        max_cap: float = 50.0,
    ) -> BundlePriceBreakdown:
        """
        Calculate the bundle discount breakdown.

        Parameters
        ----------
        subtotal             : Sum of all selected item prices × quantities.
        selected_item_count  : Total number of units (not unique products) selected.
        per_item_discount    : % discount earned per item unit (default 5).
        max_cap              : Maximum total discount cap in % (default 50).

        Returns
        -------
        BundlePriceBreakdown with all fields populated and rounded to 2 dp.
        """
        if subtotal <= 0 or selected_item_count <= 0:
            return BundlePriceBreakdown(
                subtotal=round(subtotal, 2),
                item_count=selected_item_count,
                discount_percent=0.0,
                discount_amount=0.0,
                final_price=round(subtotal, 2),
            )

        # ── Core formula ──────────────────────────────────────────────────
        discount_percent = per_item_discount * selected_item_count
        capped_percent   = min(discount_percent, max_cap)
        discount_amount  = round(subtotal * capped_percent / 100, 2)
        final_price      = round(subtotal - discount_amount, 2)

        return BundlePriceBreakdown(
            subtotal=round(subtotal, 2),
            item_count=selected_item_count,
            discount_percent=capped_percent,
            discount_amount=discount_amount,
            final_price=max(final_price, 0.0),
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
bundle_pricing_service = BundlePricingService()
