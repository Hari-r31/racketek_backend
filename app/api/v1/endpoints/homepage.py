"""
Public homepage endpoint — returns all active sections merged with live product data.
Matches the InstaSport.club layout section-for-section.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Any, Dict, List

from app.core.dependencies import get_db
from app.models.homepage import HomepageContent
from app.models.product import Product, ProductStatus
from app.schemas.homepage import DEFAULT_CONTENT, ALL_SECTIONS

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _product_to_dict(p: "Product") -> Dict[str, Any]:
    """Serialise a Product ORM object to a plain dict for JSON output."""
    if not p:
        return {}
    primary = next((img for img in (p.images or []) if img.is_primary), None)
    if not primary and p.images:
        primary = p.images[0]
    return {
        "id":                p.id,
        "name":              p.name,
        "slug":              p.slug,
        "brand":             p.brand,
        "price":             float(p.price),
        "compare_price":     float(p.compare_price) if p.compare_price else None,
        "stock":             p.stock,
        "avg_rating":        float(p.avg_rating or 0),
        "review_count":      p.review_count or 0,
        "short_description": p.short_description,
        "primary_image":     primary.url if primary else None,
        "images": [
            {"url": img.url, "is_primary": img.is_primary, "alt_text": img.alt_text}
            for img in (p.images or [])
        ],
        "variants": [
            {
                "id":             v.id,
                "name":           v.name,
                "value":          v.value,
                "price_modifier": float(v.price_modifier or 0),
                "stock":          v.stock,
                "is_active":      v.is_active,
            }
            for v in (p.variants or [])
        ],
    }


def _load_products_by_ids(
    db: Session, product_ids: List[int], active_only: bool = True
) -> Dict[int, Any]:
    """Fetch products by ID list, return ordered dict."""
    if not product_ids:
        return {}
    q = db.query(Product).filter(Product.id.in_(product_ids))
    if active_only:
        q = q.filter(Product.status == ProductStatus.ACTIVE)
    rows = q.all()
    return {p.id: _product_to_dict(p) for p in rows}


# ── Public route ──────────────────────────────────────────────────────────────

@router.get("")
def get_homepage(db: Session = Depends(get_db)):
    """
    Public — no auth required.
    Loads every homepage section from the DB (falling back to DEFAULT_CONTENT),
    then enriches product-linked sections with live product data.
    """
    # 1. Load active DB rows
    rows = db.query(HomepageContent).filter(HomepageContent.is_active == True).all()
    db_map: Dict[str, Any] = {row.section_key: row.content for row in rows}

    # 2. Merge: DB wins, DEFAULT fills gaps
    sections: Dict[str, Any] = {
        key: db_map.get(key, DEFAULT_CONTENT.get(key, {}))
        for key in ALL_SECTIONS
    }

    # ── 3. Enrich sections that reference products ────────────────────────────

    # ── featured_product ─────────────────────────────────────────────────────
    fp = dict(sections.get("featured_product", {}))
    fp_id = fp.get("product_id")
    if fp_id:
        p = db.query(Product).filter(
            Product.id == fp_id, Product.status == ProductStatus.ACTIVE
        ).first()
        if p:
            fp["product"] = _product_to_dict(p)
    sections["featured_product"] = fp

    # ── crafted_section: optional featured_product_id ────────────────────────
    cs = dict(sections.get("crafted_section", {}))
    cs_pid = cs.get("featured_product_id")
    if cs_pid:
        p = db.query(Product).filter(
            Product.id == cs_pid, Product.status == ProductStatus.ACTIVE
        ).first()
        if p:
            cs["featured_product"] = _product_to_dict(p)
    sections["crafted_section"] = cs

    # ── bundle_builder: enrich product list ──────────────────────────────────
    bb = dict(sections.get("bundle_builder", {}))
    bb_ids = bb.get("product_ids") or []
    if bb_ids:
        pm = _load_products_by_ids(db, bb_ids)
        bb["products"] = [
            pm[pid] for pid in bb_ids if pid in pm
        ]
    else:
        # Fallback: top 6 best-selling featured products
        fallback = (
            db.query(Product)
            .filter(Product.is_featured == True, Product.status == ProductStatus.ACTIVE)
            .order_by(Product.sold_count.desc())
            .limit(6)
            .all()
        )
        bb["products"] = [_product_to_dict(p) for p in fallback]
    sections["bundle_builder"] = bb

    # ── deal_of_day: enrich product list ─────────────────────────────────────
    dod = dict(sections.get("deal_of_day", {}))
    dod_ids = dod.get("product_ids") or []
    if dod_ids:
        pm = _load_products_by_ids(db, dod_ids)
        dod["products"] = [pm[pid] for pid in dod_ids if pid in pm]
    sections["deal_of_day"] = dod

    # ── shop_the_look: enrich each hotspot ───────────────────────────────────
    stl = dict(sections.get("shop_the_look", {}))
    enriched_hotspots = []
    for item in stl.get("products", []):
        item = dict(item)
        pid = item.get("product_id")
        if pid:
            p = db.query(Product).filter(
                Product.id == pid, Product.status == ProductStatus.ACTIVE
            ).first()
            if p:
                item["product"] = _product_to_dict(p)
        enriched_hotspots.append(item)
    stl["products"] = enriched_hotspots
    sections["shop_the_look"] = stl

    # ── featured_collections: enrich each tab ────────────────────────────────
    fc = dict(sections.get("featured_collections", {}))
    enriched_tabs = []
    for tab in fc.get("tabs", []):
        tab = dict(tab)
        t_ids = tab.get("product_ids") or []
        if t_ids:
            pm = _load_products_by_ids(db, t_ids)
            tab["products"] = [pm[pid] for pid in t_ids if pid in pm]
        elif fc.get("fallback_featured"):
            # Auto-fill with best-selling active products for preview
            fallback = (
                db.query(Product)
                .filter(Product.is_featured == True, Product.status == ProductStatus.ACTIVE)
                .order_by(Product.sold_count.desc())
                .limit(6)
                .all()
            )
            tab["products"] = [_product_to_dict(p) for p in fallback]
        else:
            tab["products"] = []
        enriched_tabs.append(tab)
    fc["tabs"] = enriched_tabs
    sections["featured_collections"] = fc

    return {"sections": sections}
