"""
Bundle pricing endpoint
=======================
Used EXCLUSIVELY by the Build Your Bundle UI on the homepage.
This route MUST NOT be called from normal cart or checkout flows.

Routes:
  POST /bundle/calculate  → return real-time discount breakdown
  GET  /bundle/settings   → return current discount settings (public)
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import List
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.homepage import HomepageContent
from app.schemas.homepage import DEFAULT_CONTENT, SECTION_BUNDLE_BUILDER
from app.services.bundle_pricing_service import bundle_pricing_service

router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────

class BundleItem(BaseModel):
    product_id: int
    quantity:   int   = Field(ge=1)
    price:      float = Field(ge=0)


class BundlePriceRequest(BaseModel):
    items: List[BundleItem]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_bundle_settings(db: Session) -> dict:
    """Load bundle settings from DB, fall back to schema defaults."""
    row = db.query(HomepageContent).filter(
        HomepageContent.section_key == SECTION_BUNDLE_BUILDER,
        HomepageContent.is_active   == True,
    ).first()
    settings = row.content if row else DEFAULT_CONTENT[SECTION_BUNDLE_BUILDER]
    return {
        "bundle_discount_per_item": float(settings.get("bundle_discount_per_item", 5)),
        "bundle_discount_max_cap":  float(settings.get("bundle_discount_max_cap",  50)),
        "min_items":                int(settings.get("min_items", 2)),
    }


# ── POST /bundle/calculate ────────────────────────────────────────────────────

@router.post("/calculate")
def calculate_bundle_price(
    payload: BundlePriceRequest,
    db: Session = Depends(get_db),
):
    """
    Real-time bundle price calculation.
    Called on every add / remove / quantity-change in the Bundle Builder UI.
    Completely isolated from the normal cart pricing path.
    """
    settings       = _get_bundle_settings(db)
    per_item       = settings["bundle_discount_per_item"]
    max_cap        = settings["bundle_discount_max_cap"]

    subtotal       = sum(item.price * item.quantity for item in payload.items)
    selected_count = sum(item.quantity              for item in payload.items)

    breakdown = bundle_pricing_service.calculate(
        subtotal=subtotal,
        selected_item_count=selected_count,
        per_item_discount=per_item,
        max_cap=max_cap,
    )

    return {
        "subtotal":         breakdown.subtotal,
        "item_count":       breakdown.item_count,
        "discount_percent": breakdown.discount_percent,
        "discount_amount":  breakdown.discount_amount,
        "final_price":      breakdown.final_price,
        # Pass settings back so the UI can show the "per-item" label
        "per_item_discount": per_item,
        "max_cap":           max_cap,
    }


# ── GET /bundle/settings ──────────────────────────────────────────────────────

@router.get("/settings")
def get_bundle_settings(db: Session = Depends(get_db)):
    """
    Public — returns the current bundle discount configuration.
    Used by the frontend to initialise the UI before any item is selected.
    """
    return _get_bundle_settings(db)
