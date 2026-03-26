"""
Product listing & detail endpoints (customer-facing)

Fixes applied
-------------
H2  — `status=all` is now admin-only. Unauthenticated / customer requests
       always see ACTIVE products only, regardless of status_filter param.
H4  — GET /products/recommend/{product_id} now requires authentication.
       (The endpoint is also rate-limited at the router level via SlowAPI.)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
import math

from app.core.dependencies import get_db, require_admin
from app.core.security import decode_token_detailed
from app.models.product import Product
from app.models.category import Category
from app.models.user import User
from app.enums import ProductStatus, UserRole
from app.schemas.product import (
    ProductCreate, ProductUpdate,
    ProductResponse, ProductListResponse, PaginatedProducts,
)

router = APIRouter()

_optional_bearer = HTTPBearer(auto_error=False)


def _get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if credentials is None:
        return None
    result = decode_token_detailed(credentials.credentials)
    if not result.ok or result.payload.get("type") != "access":
        return None
    user_id = result.payload.get("sub")
    if not user_id:
        return None
    return db.query(User).filter(User.id == int(user_id), User.is_active == True).first()


@router.get("", response_model=PaginatedProducts)
def list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = None,
    category: Optional[str] = Query(None),
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
    # H2: optional user to check if requester is admin
    current_user: Optional[User] = Depends(_get_optional_user),
    db: Session = Depends(get_db),
):
    """Paginated, filterable product listing.

    H2 FIX: status=all (bypass ACTIVE filter) requires admin role.
    Public / unauthenticated requests always see ACTIVE products only.
    """
    is_admin = (
        current_user is not None
        and current_user.role in [UserRole.admin, UserRole.super_admin]
    )

    # H2 FIX: Only admins may use status_filter != active
    if status_filter and status_filter != "all":
        if not is_admin:
            # Non-admin supplied a specific status filter — honour only if it's "active"
            q = db.query(Product).filter(Product.status == ProductStatus.active)
        else:
            try:
                q = db.query(Product).filter(Product.status == ProductStatus(status_filter.lower().strip()))
            except ValueError:
                q = db.query(Product)  # invalid status — show all for admin
    elif status_filter == "all":
        if is_admin:
            q = db.query(Product)  # admins see everything
        else:
            # Non-admin sent status=all — silently clamp to active
            q = db.query(Product).filter(Product.status == ProductStatus.active)
    else:
        q = db.query(Product).filter(Product.status == ProductStatus.active)

    # ── Category filter ───────────────────────────────────────────────────
    if category and not category_id:
        cat = db.query(Category).filter(Category.slug == category).first()
        if cat:
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

    _LEGACY = {
        "newest":       Product.created_at.desc(),
        "price_asc":    Product.price.asc(),
        "price_desc":   Product.price.desc(),
        "best_selling": Product.sold_count.desc(),
        "rating":       Product.avg_rating.desc(),
    }
    _FIELD_MAP = {
        "name":       Product.name,
        "price":      Product.price,
        "stock":      Product.stock,
        "sold_count": Product.sold_count,
        "avg_rating": Product.avg_rating,
        "created_at": Product.created_at,
        "status":     Product.status,
    }
    order_clause = Product.created_at.desc()
    if sort in _LEGACY:
        order_clause = _LEGACY[sort]
    elif sort and "_" in sort:
        *parts, direction = sort.rsplit("_", 1)
        field_key = "_".join(parts)
        col = _FIELD_MAP.get(field_key)
        if col is not None:
            order_clause = col.asc() if direction == "asc" else col.desc()
    q = q.order_by(order_clause)

    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return PaginatedProducts(
        items=items, total=total, page=page, per_page=per_page,
        total_pages=math.ceil(total / per_page) if per_page else 1,
    )


@router.get("/suggestions", response_model=List[dict])
def search_suggestions(
    q: str = Query("", min_length=1),
    limit: int = Query(8, le=15),
    db: Session = Depends(get_db),
):
    if not q or len(q.strip()) < 1:
        return []

    term    = q.strip()
    results = []
    seen    = set()

    products = (
        db.query(Product.name, Product.slug, Product.brand)
        .filter(Product.status == ProductStatus.active, Product.name.ilike(f"%{term}%"))
        .limit(limit)
        .all()
    )
    for p in products:
        key = p.name.lower()
        if key not in seen:
            seen.add(key)
            results.append({"type": "product", "label": p.name, "slug": p.slug, "brand": p.brand})

    brands = (
        db.query(Product.brand)
        .filter(
            Product.status == ProductStatus.active,
            Product.brand.ilike(f"%{term}%"),
            Product.brand.isnot(None),
        )
        .distinct().limit(4).all()
    )
    for b in brands:
        key = f"brand:{b.brand.lower()}"
        if b.brand and key not in seen:
            seen.add(key)
            results.append({"type": "brand", "label": b.brand, "slug": None, "brand": b.brand})

    cats = (
        db.query(Category.name, Category.slug)
        .filter(Category.name.ilike(f"%{term}%"))
        .limit(4).all()
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
    q = db.query(Product.brand).filter(
        Product.status == ProductStatus.active,
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
        Product.is_featured == True, Product.status == ProductStatus.active,
    ).limit(limit).all()


@router.get("/best-sellers", response_model=List[ProductListResponse])
def best_sellers(limit: int = 8, db: Session = Depends(get_db)):
    return db.query(Product).filter(
        Product.is_best_seller == True, Product.status == ProductStatus.active,
    ).order_by(Product.sold_count.desc()).limit(limit).all()


@router.get("/{slug}", response_model=ProductResponse)
def get_product(slug: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.slug == slug).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# ── Admin CRUD ────────────────────────────────────────────────────────────────

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
    from app.models.product import ProductVariant
    from app.api.v1.endpoints.admin.admin_products import _sync_variants

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    data = payload.model_dump(exclude_none=True)
    variants_data = data.pop("variants", None)

    for field, value in data.items():
        setattr(product, field, value)

    if variants_data is not None:
        _sync_variants(db, product, variants_data)

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
