"""
Admin inventory management
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.core.dependencies import get_db, require_admin
from app.models.user import User
from app.models.product import Product, ProductStatus
from app.schemas.product import ProductListResponse

router = APIRouter()


@router.get("/low-stock", response_model=List[ProductListResponse])
def low_stock_alert(
    threshold: int = Query(None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Products at or below their low_stock_threshold."""
    q = db.query(Product)
    if threshold is not None:
        q = q.filter(Product.stock <= threshold)
    else:
        q = q.filter(Product.stock <= Product.low_stock_threshold)
    return q.order_by(Product.stock.asc()).all()


@router.get("/out-of-stock", response_model=List[ProductListResponse])
def out_of_stock(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(Product).filter(Product.stock == 0).all()


@router.post("/bulk-stock-update")
def bulk_stock_update(
    updates: List[dict],   # [{product_id: int, stock: int}]
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update stock for multiple products at once."""
    updated = 0
    for u in updates:
        product_id = u.get("product_id")
        stock = u.get("stock", 0)
        product = db.query(Product).filter(Product.id == product_id).first()
        if product:
            product.stock = max(0, stock)
            if stock == 0:
                product.status = ProductStatus.OUT_OF_STOCK
            elif product.status == ProductStatus.OUT_OF_STOCK:
                product.status = ProductStatus.ACTIVE
            updated += 1
    db.commit()
    return {"updated": updated}


@router.get("/stock-value")
def stock_value(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Total inventory value based on cost_price."""
    products = db.query(Product).filter(Product.stock > 0).all()
    total = sum(
        (p.cost_price or p.price) * p.stock for p in products
    )
    return {
        "total_stock_value": round(total, 2),
        "total_sku_count": len(products),
        "total_units": sum(p.stock for p in products),
    }
