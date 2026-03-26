"""
Product Pydantic schemas — Catalog v2

New fields (all optional / backward-compatible):
  highlights        Optional[List[str]]
  specifications    Optional[Dict[str, Dict[str, Any]]]   ← strict validation
  manufacturer_info Optional[Dict[str, Any]]
  extra_data        Optional[Dict[str, Any]]

Validation rules for specifications
------------------------------------
  • Max 50 sections
  • Max 50 fields per section
  • Section name  : non-empty string
  • Field key     : non-empty string (after strip)
  • Value         : str | int | float | bool only (no arrays, no nested dicts)
  • No null / None values
  • Total JSON payload must not exceed 50 KB (enforced by _check_json_size helper)
"""
import json
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List, Any, Dict
from datetime import datetime
from app.enums import ProductStatus, DifficultyLevel, GenderCategory

# ── Scalar type allowed inside specifications ──────────────────────────────
_SPEC_SCALAR = (str, int, float, bool)

# ── Size caps ─────────────────────────────────────────────────────────────
_MAX_SPEC_SECTIONS   = 50
_MAX_SPEC_FIELDS     = 50
_MAX_PAYLOAD_BYTES   = 50 * 1024  # 50 KB


# ─────────────────────────────────────────────────────────────────────────────
# Shared validators (module-level so they can be reused in multiple schemas)
# ─────────────────────────────────────────────────────────────────────────────

def _validate_specifications(
    specs: Optional[Dict[str, Dict[str, Any]]]
) -> Optional[Dict[str, Dict[str, Any]]]:
    """Enforce the strict specifications schema contract."""
    if specs is None:
        return specs

    if not isinstance(specs, dict):
        raise ValueError("specifications must be a JSON object (dict).")

    # ── Payload size guard ─────────────────────────────────────────────────
    raw = json.dumps(specs, ensure_ascii=False)
    if len(raw.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
        raise ValueError(
            f"specifications payload exceeds the {_MAX_PAYLOAD_BYTES // 1024} KB limit."
        )

    # ── Section count ──────────────────────────────────────────────────────
    if len(specs) > _MAX_SPEC_SECTIONS:
        raise ValueError(
            f"specifications may have at most {_MAX_SPEC_SECTIONS} sections "
            f"(got {len(specs)})."
        )

    cleaned: Dict[str, Dict[str, Any]] = {}

    for section_name, fields in specs.items():
        if not isinstance(section_name, str) or not section_name.strip():
            raise ValueError(
                "Each section name in specifications must be a non-empty string."
            )

        if not isinstance(fields, dict):
            raise ValueError(
                f"Section '{section_name}' must be a JSON object (dict), "
                f"not {type(fields).__name__}."
            )

        if len(fields) > _MAX_SPEC_FIELDS:
            raise ValueError(
                f"Section '{section_name}' exceeds the {_MAX_SPEC_FIELDS} field limit "
                f"(got {len(fields)})."
            )

        cleaned_fields: Dict[str, Any] = {}

        for field_key, value in fields.items():
            if not isinstance(field_key, str) or not field_key.strip():
                raise ValueError(
                    f"Field keys in section '{section_name}' must be non-empty strings."
                )
            if value is None:
                raise ValueError(
                    f"Null value for key '{field_key}' in section '{section_name}' "
                    "is not allowed."
                )
            if isinstance(value, list):
                raise ValueError(
                    f"Key '{field_key}' in section '{section_name}': "
                    "arrays are not allowed as specification values. "
                    "Use a string representation instead (e.g. '100×200×300 mm')."
                )
            if isinstance(value, dict):
                raise ValueError(
                    f"Key '{field_key}' in section '{section_name}': "
                    "nested objects are not allowed as specification values. "
                    "Values must be string, number, or boolean."
                )
            if not isinstance(value, _SPEC_SCALAR):
                raise ValueError(
                    f"Key '{field_key}' in section '{section_name}': "
                    f"unsupported value type '{type(value).__name__}'. "
                    "Allowed types: string, integer, float, boolean."
                )
            cleaned_fields[field_key.strip()] = value

        cleaned[section_name.strip()] = cleaned_fields

    return cleaned


def _validate_manufacturer_info(
    info: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Validate manufacturer_info: flat dict of non-empty string keys → scalar values."""
    if info is None:
        return info

    if not isinstance(info, dict):
        raise ValueError("manufacturer_info must be a JSON object (dict).")

    raw = json.dumps(info, ensure_ascii=False)
    if len(raw.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
        raise ValueError(
            f"manufacturer_info payload exceeds the {_MAX_PAYLOAD_BYTES // 1024} KB limit."
        )

    cleaned: Dict[str, Any] = {}
    for key, value in info.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("manufacturer_info keys must be non-empty strings.")
        if value is None:
            raise ValueError(f"Null value for key '{key}' in manufacturer_info is not allowed.")
        if isinstance(value, (list, dict)):
            raise ValueError(
                f"Key '{key}' in manufacturer_info: only scalar values "
                "(string, number, boolean) are allowed."
            )
        if not isinstance(value, _SPEC_SCALAR):
            raise ValueError(
                f"Key '{key}' in manufacturer_info: unsupported value type '{type(value).__name__}'."
            )
        cleaned[key.strip()] = value

    return cleaned


def _validate_highlights(highlights: Optional[List[Any]]) -> Optional[List[str]]:
    """Validate that highlights is a list of non-empty strings."""
    if highlights is None:
        return highlights

    if not isinstance(highlights, list):
        raise ValueError("highlights must be a JSON array of strings.")

    cleaned = []
    for i, item in enumerate(highlights):
        if not isinstance(item, str):
            raise ValueError(
                f"highlights[{i}] must be a string (got {type(item).__name__})."
            )
        stripped = item.strip()
        if not stripped:
            raise ValueError(f"highlights[{i}] must not be an empty string.")
        cleaned.append(stripped)

    return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# Sub-schemas
# ─────────────────────────────────────────────────────────────────────────────

class ProductImageCreate(BaseModel):
    url: str
    public_id: Optional[str] = None
    alt_text: Optional[str] = None
    is_primary: bool = False


class ProductImageResponse(BaseModel):
    id: int
    url: str
    alt_text: Optional[str]
    is_primary: bool
    sort_order: int

    class Config:
        from_attributes = True


class ProductVariantCreate(BaseModel):
    name: str
    value: str
    sku: Optional[str] = None
    price_modifier: float = 0.0
    stock: int = 0
    is_active: bool = True


class ProductVariantUpdate(BaseModel):
    """
    Used in ProductUpdate.variants list.
    If `id` is present → update that existing variant.
    If `id` is absent  → create a new variant.
    Variants not present in the list will be deleted.
    """
    id: Optional[int] = None          # existing variant id (None = new)
    name: str
    value: str
    sku: Optional[str] = None
    price_modifier: float = 0.0
    stock: int = 0
    is_active: bool = True


class ProductVariantResponse(BaseModel):
    id: int
    name: str
    value: str
    sku: Optional[str]
    price_modifier: float
    stock: int
    is_active: bool

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# ProductCreate
# ─────────────────────────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    brand: Optional[str] = None
    sku: Optional[str] = None
    price: float
    compare_price: Optional[float] = None
    cost_price: Optional[float] = None
    category_id: Optional[int] = None
    stock: int = 0
    low_stock_threshold: int = 5
    weight: Optional[float] = None
    status: ProductStatus = ProductStatus.active
    is_featured: bool = False
    is_best_seller: bool = False
    is_returnable: bool = True
    return_window_days: int = 7
    tags: Optional[List[str]] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    difficulty_level: Optional[DifficultyLevel] = None
    gender: Optional[GenderCategory] = None

    # ── Catalog v2 ──────────────────────────────────────────────────────────
    highlights: Optional[List[str]] = None
    specifications: Optional[Dict[str, Dict[str, Any]]] = None
    manufacturer_info: Optional[Dict[str, Any]] = None
    extra_data: Optional[Dict[str, Any]] = None

    variants: List[ProductVariantCreate] = []
    images: List[ProductImageCreate] = []

    @field_validator("meta_description", mode="before")
    @classmethod
    def truncate_meta_description(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 500:
            return v[:497] + "..."
        return v

    @field_validator("short_description", mode="before")
    @classmethod
    def truncate_short_description(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 500:
            return v[:497] + "..."
        return v

    @field_validator("highlights", mode="before")
    @classmethod
    def validate_highlights(cls, v):
        return _validate_highlights(v)

    @field_validator("specifications", mode="before")
    @classmethod
    def validate_specifications(cls, v):
        return _validate_specifications(v)

    @field_validator("manufacturer_info", mode="before")
    @classmethod
    def validate_manufacturer_info(cls, v):
        return _validate_manufacturer_info(v)


# ─────────────────────────────────────────────────────────────────────────────
# ProductUpdate
# ─────────────────────────────────────────────────────────────────────────────

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    brand: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[float] = None
    compare_price: Optional[float] = None
    cost_price: Optional[float] = None
    category_id: Optional[int] = None
    stock: Optional[int] = None
    low_stock_threshold: Optional[int] = None
    weight: Optional[float] = None
    status: Optional[ProductStatus] = None
    is_featured: Optional[bool] = None
    is_best_seller: Optional[bool] = None
    is_returnable: Optional[bool] = None
    return_window_days: Optional[int] = None
    tags: Optional[List[str]] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    difficulty_level: Optional[DifficultyLevel] = None
    gender: Optional[GenderCategory] = None

    # ── Catalog v2 ──────────────────────────────────────────────────────────
    highlights: Optional[List[str]] = None
    specifications: Optional[Dict[str, Dict[str, Any]]] = None
    manufacturer_info: Optional[Dict[str, Any]] = None
    extra_data: Optional[Dict[str, Any]] = None

    # ── Variants: full replace/sync on update ──────────────────────────────
    # Sending this field triggers a full sync:
    #   - items with id  → updated in-place
    #   - items without  → created fresh
    #   - existing items not in list → deleted
    # Omit the field entirely to leave variants unchanged.
    variants: Optional[List[ProductVariantUpdate]] = None

    @field_validator("meta_description", mode="before")
    @classmethod
    def truncate_meta_description(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 500:
            return v[:497] + "..."
        return v

    @field_validator("short_description", mode="before")
    @classmethod
    def truncate_short_description(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 500:
            return v[:497] + "..."
        return v

    @field_validator("highlights", mode="before")
    @classmethod
    def validate_highlights(cls, v):
        return _validate_highlights(v)

    @field_validator("specifications", mode="before")
    @classmethod
    def validate_specifications(cls, v):
        return _validate_specifications(v)

    @field_validator("manufacturer_info", mode="before")
    @classmethod
    def validate_manufacturer_info(cls, v):
        return _validate_manufacturer_info(v)


# ─────────────────────────────────────────────────────────────────────────────
# ProductResponse
# ─────────────────────────────────────────────────────────────────────────────

class ProductResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    short_description: Optional[str]
    brand: Optional[str]
    sku: Optional[str]
    price: float
    compare_price: Optional[float]
    category_id: Optional[int]
    stock: int
    status: ProductStatus
    is_featured: bool
    is_best_seller: bool
    is_returnable: bool = True
    return_window_days: int = 7
    avg_rating: float
    review_count: int
    sold_count: int
    tags: Optional[List[str]]
    difficulty_level: Optional[DifficultyLevel] = None
    gender: Optional[GenderCategory] = None

    # ── Catalog v2 ──────────────────────────────────────────────────────────
    highlights: Optional[List[str]] = None
    specifications: Optional[Dict[str, Dict[str, Any]]] = None
    manufacturer_info: Optional[Dict[str, Any]] = None
    extra_data: Optional[Dict[str, Any]] = None

    images: List[ProductImageResponse] = []
    variants: List[ProductVariantResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
# ProductListResponse  (lighter payload for listing pages)
# ─────────────────────────────────────────────────────────────────────────────

class ProductListResponse(BaseModel):
    id: int
    name: str
    slug: str
    brand: Optional[str]
    sku: Optional[str] = None
    price: float
    compare_price: Optional[float]
    stock: int
    low_stock_threshold: int = 5
    status: ProductStatus
    avg_rating: float
    review_count: int
    sold_count: int = 0
    is_featured: bool
    is_best_seller: bool
    is_returnable: bool = True
    return_window_days: int = 7
    category_id: Optional[int] = None
    difficulty_level: Optional[DifficultyLevel] = None
    gender: Optional[GenderCategory] = None
    highlights: Optional[List[str]] = None
    images: List[ProductImageResponse] = []

    class Config:
        from_attributes = True


class PaginatedProducts(BaseModel):
    items: List[ProductListResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
