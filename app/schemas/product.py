from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from app.models.product import ProductStatus


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
    status: ProductStatus = ProductStatus.ACTIVE
    is_featured: bool = False
    is_best_seller: bool = False
    tags: Optional[List[str]] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    variants: List[ProductVariantCreate] = []


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
    tags: Optional[List[str]] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


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
    avg_rating: float
    review_count: int
    sold_count: int
    tags: Optional[List[str]]
    images: List[ProductImageResponse] = []
    variants: List[ProductVariantResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    id: int
    name: str
    slug: str
    brand: Optional[str]
    price: float
    compare_price: Optional[float]
    stock: int
    status: ProductStatus
    avg_rating: float
    review_count: int
    is_featured: bool
    is_best_seller: bool
    images: List[ProductImageResponse] = []

    class Config:
        from_attributes = True


class PaginatedProducts(BaseModel):
    items: List[ProductListResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
