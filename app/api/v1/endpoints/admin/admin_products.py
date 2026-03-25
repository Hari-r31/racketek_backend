"""
Admin product management
FEATURE 1: Full bulk-upload via CSV or Excel with validation & reporting
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import Optional, List
import csv
import io
import math
import re

from app.core.dependencies import get_db, require_admin
from app.models.user import User
from app.models.product import Product, ProductStatus, DifficultyLevel, GenderCategory
from app.models.product import ProductVariant
from app.models.category import Category
from app.schemas.product import (
    ProductCreate, ProductResponse, PaginatedProducts,
    ProductListResponse, ProductUpdate,
)

router = APIRouter()


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    """Convert any string to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def _ensure_unique_slug(db: Session, base_slug: str, exclude_id: int | None = None) -> str:
    """Append numeric suffix until slug is unique in DB."""
    slug = base_slug
    counter = 1
    while True:
        q = db.query(Product).filter(Product.slug == slug)
        if exclude_id:
            q = q.filter(Product.id != exclude_id)
        if not q.first():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def _parse_rows(file_content: bytes, filename: str) -> tuple[list[dict], str | None]:
    """
    Parse uploaded file into a list of row dicts.
    Supports CSV and Excel (.xlsx).
    Returns (rows, error_message).
    """
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "csv":
        try:
            text = file_content.decode("utf-8-sig")  # handle BOM
            reader = csv.DictReader(io.StringIO(text))
            return list(reader), None
        except Exception as e:
            return [], f"Could not parse CSV: {e}"

    elif ext in ("xlsx", "xls"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file_content), read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                return [], "Excel file is empty"
            headers = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
            result = []
            for row in rows[1:]:
                if all(v is None for v in row):
                    continue
                result.append({headers[i]: (str(v).strip() if v is not None else "") for i, v in enumerate(row)})
            return result, None
        except ImportError:
            return [], "openpyxl is required for Excel uploads. Install it with: pip install openpyxl"
        except Exception as e:
            return [], f"Could not parse Excel file: {e}"

    else:
        return [], f"Unsupported file type '.{ext}'. Supported: CSV (.csv) and Excel (.xlsx)"


def _normalize_header(h: str) -> str:
    """Normalize header: lowercase, replace spaces/special chars with underscore."""
    return re.sub(r"[^a-z0-9]+", "_", h.lower().strip()).strip("_")


def _get(row: dict, *keys: str, default: str = "") -> str:
    """Try multiple key variants (original + normalized)."""
    for k in keys:
        if k in row:
            return str(row[k]).strip()
        nk = _normalize_header(k)
        for rk in row:
            if _normalize_header(rk) == nk:
                return str(row[rk]).strip()
    return default


# ────────────────────────────────────────────────────────────────────────────
# Product search (must be before /{product_id})
# ────────────────────────────────────────────────────────────────────────────

@router.get("/search")
def search_products(
    q: str = Query("", description="Search term — matches name, sku, or category"),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from sqlalchemy import or_
    q_stripped = (q or "").strip()
    if len(q_stripped) < 1:
        return []
    pattern = f"%{q_stripped}%"
    rows = (
        db.query(
            Product.id, Product.name, Product.sku,
            Product.price, Product.stock, Product.status,
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
        {"id": r.id, "name": r.name, "sku": r.sku, "price": r.price,
         "stock": r.stock, "status": r.status, "category_name": r.category_name}
        for r in rows
    ]


# ────────────────────────────────────────────────────────────────────────────
# CRUD
# ────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedProducts)
def admin_list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = Query(None),
    sort: Optional[str] = Query("created_at_desc"),
    difficulty_level: Optional[str] = None,
    gender: Optional[str] = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Product)
    if search:
        q = q.filter(Product.name.ilike(f"%{search}%"))
    if status and status != "all":
        q = q.filter(Product.status == status)
    if gender and gender != "all":
        q = q.filter(Product.gender == gender)
    if difficulty_level and difficulty_level != "all":
        q = q.filter(Product.difficulty_level == difficulty_level)

    _FIELD_MAP = {
        "name": Product.name, "price": Product.price, "stock": Product.stock,
        "sold_count": Product.sold_count, "avg_rating": Product.avg_rating,
        "created_at": Product.created_at, "status": Product.status,
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


@router.get("/low-stock", response_model=List[ProductListResponse])
def low_stock_products(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(Product).filter(
        Product.stock <= Product.low_stock_threshold
    ).order_by(Product.stock.asc()).all()


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

    data = payload.model_dump(exclude_none=True)

    # ── Extract variants before applying scalar fields ─────────────────────
    # variants is a SQLAlchemy relationship — it cannot be set via setattr
    # with plain dicts.  Handle it explicitly.
    variants_data = data.pop("variants", None)

    # ── Apply all scalar / JSON column fields ──────────────────────────────
    for field, value in data.items():
        setattr(product, field, value)

    # ── Sync variants ──────────────────────────────────────────────────────
    if variants_data is not None:
        _sync_variants(db, product, variants_data)

    db.commit()
    db.refresh(product)
    return product


def _sync_variants(db: Session, product: Product, variants_data: list[dict]) -> None:
    """
    Reconcile the variants_data list against the existing ProductVariant rows.

    Strategy:
      • A variant dict with an "id" key → UPDATE that existing variant in-place.
      • A variant dict without an "id"  → CREATE a new variant.
      • Existing variants whose id is NOT in the incoming list → DELETE them.

    This preserves variant ids (important for cart / order references) while
    allowing the admin to add, remove, or edit variants freely.
    """
    incoming_ids: set[int] = set()

    for v_data in variants_data:
        variant_id = v_data.get("id")

        if variant_id:
            # UPDATE existing variant
            variant = db.query(ProductVariant).filter(
                ProductVariant.id == variant_id,
                ProductVariant.product_id == product.id,
            ).first()
            if variant:
                for k, v in v_data.items():
                    if k != "id":
                        setattr(variant, k, v)
                incoming_ids.add(variant_id)
            # If the id wasn't found on this product, treat as a new variant
            else:
                new_v = ProductVariant(
                    product_id=product.id,
                    name=v_data.get("name", ""),
                    value=v_data.get("value", ""),
                    price_modifier=v_data.get("price_modifier", 0.0),
                    stock=v_data.get("stock", 0),
                    is_active=v_data.get("is_active", True),
                )
                db.add(new_v)
        else:
            # CREATE new variant
            new_v = ProductVariant(
                product_id=product.id,
                name=v_data.get("name", ""),
                value=v_data.get("value", ""),
                price_modifier=v_data.get("price_modifier", 0.0),
                stock=v_data.get("stock", 0),
                is_active=v_data.get("is_active", True),
            )
            db.add(new_v)

    # DELETE variants that were not present in the incoming payload
    existing_variants = db.query(ProductVariant).filter(
        ProductVariant.product_id == product.id
    ).all()
    for existing in existing_variants:
        if existing.id not in incoming_ids:
            # Only delete if its id was actually tracked
            # (i.e. it had an id — we skip newly added ones that have no id yet)
            db.delete(existing)


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


# ────────────────────────────────────────────────────────────────────────────
# FEATURE 1 — Bulk Upload (CSV + Excel)
# ────────────────────────────────────────────────────────────────────────────

@router.post("/bulk-upload")
async def bulk_upload_products(
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Bulk upload products via CSV or Excel.

    Supported columns (case-insensitive, spaces OK):
        S.NO / s_no              — row number (optional, informational)
        Category                 — parent category name (matched or created)
        Sub_Category             — sub-category name (matched or created)
        Product Name / name      — required
        Product details / description
        Quantity / stock         — numeric, default 0
        Product Image location / image_url
        Sub_Image location / sub_image_url
        Extra details / short_description
        Item code / sku / item_code
        Key Features / tags
        Price / price            — numeric, default 0
        Brand / brand
        Difficulty / difficulty_level   — beginner / intermediate / advanced
        Gender / gender          — male / female / unisex / boys / girls

    Returns:
        success_count, failed_count, error_rows[]
    """
    filename = file.filename or "upload"
    contents = await file.read()

    rows, parse_error = _parse_rows(contents, filename)
    if parse_error:
        raise HTTPException(status_code=400, detail=parse_error)
    if not rows:
        raise HTTPException(status_code=400, detail="File is empty or has no data rows")

    # Build category lookup cache {name_lower: id}
    cat_cache: dict[str, int] = {
        c.name.lower(): c.id
        for c in db.query(Category).all()
    }

    success_count = 0
    failed_count = 0
    error_rows: list[dict] = []

    # Collect already-used SKUs in this batch to detect intra-batch duplicates
    used_skus_in_batch: set[str] = set()

    for row_num, row in enumerate(rows, start=2):  # start=2 accounts for header row
        row_errors: list[str] = []

        # ── Extract fields ───────────────────────────────────────────────────
        sno          = _get(row, "S.NO", "s_no", "sno", default=str(row_num))
        name         = _get(row, "Product Name", "name", "product_name")
        description  = _get(row, "Product details", "description", "product_details")
        short_desc   = _get(row, "Extra details", "short_description", "extra_details")
        qty_str      = _get(row, "Quantity", "stock", "qty", default="0")
        price_str    = _get(row, "Price", "price", default="0")
        image_url    = _get(row, "Product Image location", "image_url", "product_image_location")
        sub_image    = _get(row, "Sub_Image location", "sub_image_url", "sub_image_location")
        sku          = _get(row, "Item code", "sku", "item_code")
        tags_str     = _get(row, "Key Features", "tags", "key_features")
        brand        = _get(row, "Brand", "brand")
        cat_name     = _get(row, "Category", "category")
        subcat_name  = _get(row, "Sub_Category", "sub_category", "subcategory")
        difficulty   = _get(row, "Difficulty", "difficulty_level").lower() or None
        gender_val   = _get(row, "Gender", "gender").lower() or None

        # ── Validate required fields ─────────────────────────────────────────
        if not name:
            row_errors.append("Product Name is required")

        # ── Validate quantity ────────────────────────────────────────────────
        try:
            stock = int(float(qty_str)) if qty_str else 0
            if stock < 0:
                row_errors.append("Quantity cannot be negative")
        except ValueError:
            row_errors.append(f"Quantity '{qty_str}' is not numeric")
            stock = 0

        # ── Validate price ───────────────────────────────────────────────────
        try:
            price = float(price_str) if price_str else 0.0
            if price < 0:
                row_errors.append("Price cannot be negative")
        except ValueError:
            row_errors.append(f"Price '{price_str}' is not numeric")
            price = 0.0

        # ── Validate SKU uniqueness ──────────────────────────────────────────
        if sku:
            if sku in used_skus_in_batch:
                row_errors.append(f"SKU '{sku}' is duplicated within this upload")
            elif db.query(Product).filter(Product.sku == sku).first():
                row_errors.append(f"SKU '{sku}' already exists in database")
            else:
                used_skus_in_batch.add(sku)

        # ── Validate difficulty_level ────────────────────────────────────────
        valid_difficulties = {e.value for e in DifficultyLevel}
        if difficulty and difficulty not in valid_difficulties:
            row_errors.append(
                f"Invalid difficulty '{difficulty}'. Must be one of: {', '.join(valid_difficulties)}"
            )
            difficulty = None

        # ── Validate gender ──────────────────────────────────────────────────
        valid_genders = {e.value for e in GenderCategory}
        if gender_val and gender_val not in valid_genders:
            row_errors.append(
                f"Invalid gender '{gender_val}'. Must be one of: {', '.join(valid_genders)}"
            )
            gender_val = None

        # ── Validate image URLs ──────────────────────────────────────────────
        images_payload = []
        if image_url:
            if not (image_url.startswith("http") or image_url.startswith("/")):
                row_errors.append(f"Primary image URL appears invalid: '{image_url}'")
            else:
                images_payload.append({
                    "url": image_url, "is_primary": True, "alt_text": name or ""
                })
        if sub_image:
            if image_url and (sub_image.startswith("http") or sub_image.startswith("/")):
                images_payload.append({
                    "url": sub_image, "is_primary": False, "alt_text": f"{name} - sub"
                })

        # ── If any hard errors, skip row ─────────────────────────────────────
        if row_errors:
            failed_count += 1
            error_rows.append({
                "row": row_num,
                "s_no": sno,
                "name": name or "(empty)",
                "errors": row_errors,
            })
            continue

        # ── Resolve category ─────────────────────────────────────────────────
        category_id = None
        lookup_name = subcat_name or cat_name
        if lookup_name:
            category_id = cat_cache.get(lookup_name.lower())
            if not category_id:
                parent_id = None
                if subcat_name and cat_name:
                    parent_id = cat_cache.get(cat_name.lower())
                    if not parent_id:
                        parent_cat = Category(
                            name=cat_name,
                            slug=_ensure_unique_slug(db, _slugify(cat_name)),
                            is_active=True,
                        )
                        db.add(parent_cat)
                        db.flush()
                        cat_cache[cat_name.lower()] = parent_cat.id
                        parent_id = parent_cat.id

                new_cat = Category(
                    name=lookup_name,
                    slug=_ensure_unique_slug(db, _slugify(lookup_name)),
                    parent_id=parent_id,
                    is_active=True,
                )
                db.add(new_cat)
                db.flush()
                cat_cache[lookup_name.lower()] = new_cat.id
                category_id = new_cat.id

        # ── Parse tags ───────────────────────────────────────────────────────
        tags = None
        if tags_str:
            tags = [t.strip() for t in re.split(r"[,|;]", tags_str) if t.strip()]

        # ── Build slug ───────────────────────────────────────────────────────
        base_slug = _slugify(name)
        slug = _ensure_unique_slug(db, base_slug)

        # ── Create product ───────────────────────────────────────────────────
        try:
            from app.models.product import ProductImage

            product = Product(
                name=name,
                slug=slug,
                description=description or None,
                short_description=short_desc or None,
                brand=brand or None,
                sku=sku or None,
                price=price,
                stock=stock,
                category_id=category_id,
                status=ProductStatus.ACTIVE if stock > 0 else ProductStatus.OUT_OF_STOCK,
                tags=tags,
                difficulty_level=difficulty,
                gender=gender_val,
            )
            db.add(product)
            db.flush()  # get product.id

            for img_data in images_payload:
                db.add(ProductImage(
                    product_id=product.id,
                    url=img_data["url"],
                    alt_text=img_data.get("alt_text", ""),
                    is_primary=img_data["is_primary"],
                    sort_order=0 if img_data["is_primary"] else 1,
                ))

            success_count += 1

        except Exception as e:
            db.rollback()
            failed_count += 1
            error_rows.append({
                "row": row_num,
                "s_no": sno,
                "name": name,
                "errors": [f"Database error: {str(e)}"],
            })
            continue

    # Commit all successful rows in one shot
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Batch commit failed: {str(e)}"
        )

    return {
        "success_count": success_count,
        "failed_count": failed_count,
        "total_rows": len(rows),
        "error_rows": error_rows,
        "message": (
            f"Import complete: {success_count} products created, "
            f"{failed_count} rows skipped."
        ),
    }
