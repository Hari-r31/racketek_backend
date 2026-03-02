"""
Admin inventory management — fixed paginated endpoint the frontend expects
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import math

from app.core.dependencies import get_db, require_admin
from app.models.user import User
from app.models.product import Product, ProductStatus
from app.schemas.product import ProductListResponse

router = APIRouter()


# ── Main paginated endpoint expected by frontend ────────────────────────────
@router.get("")
def list_inventory(
    filter: str = Query("all"),   # "all" | "low" | "out"
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Paginated inventory list with filter support — used by admin UI."""
    q = db.query(Product)

    if filter == "low":
        q = q.filter(Product.stock > 0, Product.stock <= Product.low_stock_threshold)
    elif filter == "out":
        q = q.filter(Product.stock == 0)
    # "all" → no additional filter

    if search:
        q = q.filter(
            Product.name.ilike(f"%{search}%") | Product.sku.ilike(f"%{search}%")
        )

    total = q.count()
    items = q.order_by(Product.stock.asc()).offset((page - 1) * per_page).limit(per_page).all()

    def to_dict(p: Product):
        return {
            "id":                  p.id,
            "name":                p.name,
            "sku":                 p.sku,
            "brand":               p.brand,
            "stock":               p.stock,
            "low_stock_threshold": p.low_stock_threshold,
            "status":              p.status.value if p.status else "active",
            "sold_count":          p.sold_count,
            "price":               p.price,
            "images": [
                {"url": img.url, "is_primary": img.is_primary}
                for img in p.images
            ],
        }

    return {
        "items": [to_dict(p) for p in items],
        "total": total,
        "page":  page,
        "per_page": per_page,
        "total_pages": math.ceil(total / per_page) if per_page else 1,
    }


@router.post("/bulk-update")
def bulk_stock_update(
    payload: dict,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update stock for multiple products at once. Body: {updates: [{product_id, stock}]}"""
    updates = payload.get("updates", [])
    updated = 0
    for u in updates:
        product_id = u.get("product_id")
        stock = u.get("stock", 0)
        product = db.query(Product).filter(Product.id == product_id).first()
        if product:
            product.stock = max(0, int(stock))
            if product.stock == 0:
                product.status = ProductStatus.OUT_OF_STOCK
            elif product.status == ProductStatus.OUT_OF_STOCK:
                product.status = ProductStatus.ACTIVE
            updated += 1
    db.commit()
    return {"updated": updated}


@router.get("/low-stock")
def low_stock_alert(
    threshold: Optional[int] = Query(None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Product)
    if threshold is not None:
        q = q.filter(Product.stock <= threshold)
    else:
        q = q.filter(Product.stock <= Product.low_stock_threshold)
    return q.order_by(Product.stock.asc()).all()


@router.get("/out-of-stock")
def out_of_stock(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(Product).filter(Product.stock == 0).all()


@router.get("/stock-value")
def stock_value(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    products = db.query(Product).filter(Product.stock > 0).all()
    total = sum((p.cost_price or p.price) * p.stock for p in products)
    return {
        "total_stock_value": round(total, 2),
        "total_sku_count":   len(products),
        "total_units":       sum(p.stock for p in products),
    }
