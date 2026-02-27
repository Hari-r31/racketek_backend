"""
Product listing & detail endpoints (customer-facing)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
import math

from app.core.dependencies import get_db, require_admin
from app.models.product import Product, ProductStatus
from app.models.user import User
from app.schemas.product import (
    ProductCreate, ProductUpdate,
    ProductResponse, ProductListResponse, PaginatedProducts,
)

router = APIRouter()


@router.get("", response_model=PaginatedProducts)
def list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = None,
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_rating: Optional[float] = None,
    in_stock: Optional[bool] = None,
    is_featured: Optional[bool] = None,
    is_best_seller: Optional[bool] = None,
    search: Optional[str] = None,
    sort: Optional[str] = Query("newest", regex="^(newest|price_asc|price_desc|best_selling|rating)$"),
    db: Session = Depends(get_db),
):
    """Paginated, filterable product listing."""
    q = db.query(Product).filter(Product.status == ProductStatus.ACTIVE)

    if category_id:
        q = q.filter(Product.category_id == category_id)
    if brand:
        q = q.filter(Product.brand.ilike(f"%{brand}%"))
    if min_price is not None:
        q = q.filter(Product.price >= min_price)
    if max_price is not None:
        q = q.filter(Product.price <= max_price)
    if min_rating is not None:
        q = q.filter(Product.avg_rating >= min_rating)
    if in_stock is True:
        q = q.filter(Product.stock > 0)
    if is_featured is not None:
        q = q.filter(Product.is_featured == is_featured)
    if is_best_seller is not None:
        q = q.filter(Product.is_best_seller == is_best_seller)
    if search:
        q = q.filter(
            or_(
                Product.name.ilike(f"%{search}%"),
                Product.brand.ilike(f"%{search}%"),
                Product.description.ilike(f"%{search}%"),
            )
        )

    # Sorting
    sort_map = {
        "newest": Product.created_at.desc(),
        "price_asc": Product.price.asc(),
        "price_desc": Product.price.desc(),
        "best_selling": Product.sold_count.desc(),
        "rating": Product.avg_rating.desc(),
    }
    q = q.order_by(sort_map.get(sort, Product.created_at.desc()))

    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return PaginatedProducts(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=math.ceil(total / per_page) if per_page else 1,
    )


@router.get("/featured", response_model=List[ProductListResponse])
def featured_products(limit: int = 8, db: Session = Depends(get_db)):
    return db.query(Product).filter(
        Product.is_featured == True,
        Product.status == ProductStatus.ACTIVE,
    ).limit(limit).all()


@router.get("/best-sellers", response_model=List[ProductListResponse])
def best_sellers(limit: int = 8, db: Session = Depends(get_db)):
    return db.query(Product).filter(
        Product.is_best_seller == True,
        Product.status == ProductStatus.ACTIVE,
    ).order_by(Product.sold_count.desc()).limit(limit).all()


@router.get("/{slug}", response_model=ProductResponse)
def get_product(slug: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.slug == slug).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# ── Admin CRUD ───────────────────────────────────────────────────────────────

@router.post("", response_model=ProductResponse, status_code=201)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    exists = db.query(Product).filter(Product.slug == payload.slug).first()
    if exists:
        raise HTTPException(status_code=400, detail="Slug already taken")

    variants_data = payload.model_dump().pop("variants", [])
    product_data = {k: v for k, v in payload.model_dump().items() if k != "variants"}
    product = Product(**product_data)
    db.add(product)
    db.flush()

    from app.models.product import ProductVariant
    for v in variants_data:
        db.add(ProductVariant(product_id=product.id, **v))

    db.commit()
    db.refresh(product)
    return product


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
