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
from app.models.category import Category
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
    category: Optional[str] = Query(None, description="Category slug — resolves to category_id automatically, includes sub-categories"),
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_rating: Optional[float] = None,
    in_stock: Optional[bool] = None,
    is_featured: Optional[bool] = None,
    is_best_seller: Optional[bool] = None,
    search: Optional[str] = None,
    sort: Optional[str] = Query("newest"),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    """Paginated, filterable product listing."""
    # Admin pages send status=all to bypass the active-only filter
    if status_filter and status_filter != "all":
        q = db.query(Product).filter(Product.status == status_filter)
    elif not status_filter:
        q = db.query(Product).filter(Product.status == ProductStatus.ACTIVE)
    else:
        q = db.query(Product)  # status=all: no filter

    # ── Resolve category slug → IDs (include parent + all children) ──────────
    if category and not category_id:
        cat = db.query(Category).filter(Category.slug == category).first()
        if cat:
            # collect this category + all direct children
            cat_ids = [cat.id] + [c.id for c in (cat.children or [])]
            q = q.filter(Product.category_id.in_(cat_ids))
    elif category_id:
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

    # Sorting — accepts legacy values (newest, price_asc …) AND new field_dir format
    _LEGACY = {
        "newest":       Product.created_at.desc(),
        "price_asc":    Product.price.asc(),
        "price_desc":   Product.price.desc(),
        "best_selling": Product.sold_count.desc(),
        "rating":       Product.avg_rating.desc(),
    }
    _FIELD_MAP = {
        "name":         Product.name,
        "price":        Product.price,
        "stock":        Product.stock,
        "sold_count":   Product.sold_count,
        "avg_rating":   Product.avg_rating,
        "created_at":   Product.created_at,
        "status":       Product.status,
    }
    order_clause = Product.created_at.desc()   # safe default
    if sort in _LEGACY:
        order_clause = _LEGACY[sort]
    elif sort and "_" in sort:
        # e.g. "created_at_desc" → field=created_at, dir=desc
        *parts, direction = sort.rsplit("_", 1)
        field_key = "_".join(parts)
        col = _FIELD_MAP.get(field_key)
        if col is not None:
            order_clause = col.asc() if direction == "asc" else col.desc()
    q = q.order_by(order_clause)

    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return PaginatedProducts(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=math.ceil(total / per_page) if per_page else 1,
    )


@router.get("/suggestions", response_model=List[dict])
def search_suggestions(
    q: str = Query("", min_length=1),
    limit: int = Query(8, le=15),
    db: Session = Depends(get_db),
):
    """
    Fast autocomplete suggestions for the search bar.
    Returns product names + brands + category matches.
    """
    if not q or len(q.strip()) < 1:
        return []

    term = q.strip()
    results = []
    seen = set()

    # Product name matches
    products = (
        db.query(Product.name, Product.slug, Product.brand)
        .filter(
            Product.status == ProductStatus.ACTIVE,
            Product.name.ilike(f"%{term}%"),
        )
        .limit(limit)
        .all()
    )
    for p in products:
        key = p.name.lower()
        if key not in seen:
            seen.add(key)
            results.append({"type": "product", "label": p.name, "slug": p.slug, "brand": p.brand})

    # Brand matches
    brands = (
        db.query(Product.brand)
        .filter(
            Product.status == ProductStatus.ACTIVE,
            Product.brand.ilike(f"%{term}%"),
            Product.brand.isnot(None),
        )
        .distinct()
        .limit(4)
        .all()
    )
    for b in brands:
        key = f"brand:{b.brand.lower()}"
        if b.brand and key not in seen:
            seen.add(key)
            results.append({"type": "brand", "label": b.brand, "slug": None, "brand": b.brand})

    # Category matches
    cats = (
        db.query(Category.name, Category.slug)
        .filter(Category.name.ilike(f"%{term}%"))
        .limit(4)
        .all()
    )
    for c in cats:
        key = f"cat:{c.slug}"
        if key not in seen:
            seen.add(key)
            results.append({"type": "category", "label": c.name, "slug": c.slug, "brand": None})

    return results[:limit]


@router.get("/brands", response_model=List[str])
def list_brands(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Distinct brand names for the filter sidebar — no per_page limit."""
    q = db.query(Product.brand).filter(
        Product.status == ProductStatus.ACTIVE,
        Product.brand.isnot(None),
    )
    if category:
        cat = db.query(Category).filter(Category.slug == category).first()
        if cat:
            cat_ids = [cat.id] + [c.id for c in (cat.children or [])]
            q = q.filter(Product.category_id.in_(cat_ids))
    brands = [row.brand for row in q.distinct().all() if row.brand]
    return sorted(set(brands))


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

    dump = payload.model_dump()
    variants_data = dump.pop("variants", [])
    images_data   = dump.pop("images",   [])
    product = Product(**dump)
    db.add(product)
    db.flush()

    from app.models.product import ProductVariant, ProductImage
    for v in variants_data:
        db.add(ProductVariant(product_id=product.id, **v))
    for img in images_data:
        db.add(ProductImage(
            product_id=product.id,
            url=img["url"],
            public_id=img.get("public_id"),
            alt_text=img.get("alt_text") or product.name,
            is_primary=img.get("is_primary", False),
        ))

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
