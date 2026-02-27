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


@router.get("", response_model=PaginatedProducts)
def admin_list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[ProductStatus] = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Product)
    if search:
        q = q.filter(Product.name.ilike(f"%{search}%"))
    if status:
        q = q.filter(Product.status == status)
    q = q.order_by(Product.created_at.desc())
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    return PaginatedProducts(
        items=items, total=total, page=page, per_page=per_page,
        total_pages=math.ceil(total / per_page) if per_page else 1,
    )


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
