"""
Admin product management (bulk upload, stock control)
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import Optional, List
import csv
import io
import math

from app.core.dependencies import get_db, require_admin
from app.models.user import User
from app.models.product import Product, ProductStatus
from app.schemas.product import ProductResponse, PaginatedProducts, ProductListResponse, ProductUpdate

router = APIRouter()


# ── Product search (must be declared BEFORE /{product_id}) ───────────────────
@router.get("/search")
def search_products(
    q: str = Query("", description="Search term — matches name, sku, or category"),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Typeahead search for the admin autocomplete selector.
    Returns up to 10 products matching the query against:
      • products.name
      • products.sku
      • categories.name (via join — no N+1)
    """
    from app.models.category import Category
    from sqlalchemy import or_

    q_stripped = (q or "").strip()
    if len(q_stripped) < 1:
        return []

    pattern = f"%{q_stripped}%"

    rows = (
        db.query(
            Product.id,
            Product.name,
            Product.sku,
            Product.price,
            Product.stock,
            Product.status,
            Category.name.label("category_name"),
        )
        .outerjoin(Category, Product.category_id == Category.id)
        .filter(
            or_(
                Product.name.ilike(pattern),
                Product.sku.ilike(pattern),
                Category.name.ilike(pattern),
            )
        )
        .order_by(Product.name.asc())
        .limit(10)
        .all()
    )

    return [
        {
            "id":            r.id,
            "name":          r.name,
            "sku":           r.sku,
            "price":         r.price,
            "stock":         r.stock,
            "status":        r.status,
            "category_name": r.category_name,
        }
        for r in rows
    ]


@router.get("", response_model=PaginatedProducts)
def admin_list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = Query(None),
    sort: Optional[str] = Query("created_at_desc"),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Product)
    if search:
        q = q.filter(Product.name.ilike(f"%{search}%"))
    if status and status != "all":
        q = q.filter(Product.status == status)

    # Sortable columns
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
    if sort and "_" in sort:
        *parts, direction = sort.rsplit("_", 1)
        col = _FIELD_MAP.get("_".join(parts))
        if col is not None:
            order_clause = col.asc() if direction == "asc" else col.desc()
    q = q.order_by(order_clause)

    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return PaginatedProducts(
        items=items, total=total, page=page, per_page=per_page,
        total_pages=math.ceil(total / per_page) if per_page else 1,
    )


@router.get("/{product_id}", response_model=ProductResponse)
def admin_get_product(
    product_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.put("/{product_id}", response_model=ProductResponse)
def admin_update_product(
    product_id: int,
    payload: ProductUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
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
def admin_delete_product(
    product_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()


@router.patch("/{product_id}/toggle")
def toggle_product(
    product_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.status = (
        ProductStatus.INACTIVE if product.status == ProductStatus.ACTIVE else ProductStatus.ACTIVE
    )
    db.commit()
    return {"status": product.status}


@router.patch("/{product_id}/stock")
def update_stock(
    product_id: int,
    stock: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.stock = stock
    if stock == 0:
        product.status = ProductStatus.OUT_OF_STOCK
    elif product.status == ProductStatus.OUT_OF_STOCK:
        product.status = ProductStatus.ACTIVE
    db.commit()
    return {"stock": product.stock, "status": product.status}


@router.get("/low-stock", response_model=List[ProductListResponse])
def low_stock_products(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(Product).filter(
        Product.stock <= Product.low_stock_threshold
    ).order_by(Product.stock.asc()).all()


@router.post("/bulk-upload")
async def bulk_upload_products(
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    CSV bulk upload. Expected columns:
    name, slug, price, stock, brand, category_id, status, description
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    contents = await file.read()
    text = contents.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    created, skipped = 0, 0
    for row in reader:
        slug = row.get("slug", "").strip()
        if not slug:
            skipped += 1
            continue
        existing = db.query(Product).filter(Product.slug == slug).first()
        if existing:
            skipped += 1
            continue
        try:
            product = Product(
                name=row.get("name", slug),
                slug=slug,
                price=float(row.get("price", 0)),
                stock=int(row.get("stock", 0)),
                brand=row.get("brand", None),
                description=row.get("description", None),
            )
            db.add(product)
            created += 1
        except Exception:
            skipped += 1

    db.commit()
    return {"created": created, "skipped": skipped}
