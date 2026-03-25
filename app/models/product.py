"""
Product, ProductVariant, and ProductImage models

Catalog v2 additions (migration 017):
  highlights        — JSONB List[str] — bullet-point features
  specifications    — JSONB Dict[str, Dict[str, Any]] — grouped specs
  manufacturer_info — JSONB Dict[str, Any] — brand / compliance data
  extra_data        — JSONB Dict[str, Any] — extensible future fields

ENUM FIX: status, difficulty_level, gender use String (VARCHAR) — no PostgreSQL
          native enum types. Python enums are kept for validation in schemas/endpoints.
"""
import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey,
    Text, Boolean, JSON, Index,
)
from sqlalchemy.orm import relationship
from app.db.base_class import Base

# Use JSONB when PostgreSQL is available; fall back to JSON for SQLite in tests
try:
    from sqlalchemy.dialects.postgresql import JSONB
    _JSON = JSONB
except ImportError:           # pragma: no cover
    _JSON = JSON               # fallback for non-pg environments


class ProductStatus(str, enum.Enum):
    ACTIVE       = "active"
    INACTIVE     = "inactive"
    OUT_OF_STOCK = "out_of_stock"
    DRAFT        = "draft"


class DifficultyLevel(str, enum.Enum):
    BEGINNER     = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED     = "advanced"


class GenderCategory(str, enum.Enum):
    MALE   = "male"
    FEMALE = "female"
    UNISEX = "unisex"
    BOYS   = "boys"
    GIRLS  = "girls"


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(300), nullable=False, index=True)
    slug = Column(String(350), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    short_description = Column(String(500), nullable=True)
    brand = Column(String(150), nullable=True)
    sku = Column(String(100), unique=True, nullable=True)
    price = Column(Float, nullable=False)
    compare_price = Column(Float, nullable=True)  # original MRP
    cost_price = Column(Float, nullable=True)      # for margin calculation
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    stock = Column(Integer, default=0)
    low_stock_threshold = Column(Integer, default=5)
    weight = Column(Float, nullable=True)  # in kg
    status = Column(String(20), default=ProductStatus.ACTIVE.value, index=True)
    is_featured = Column(Boolean, default=False)
    is_best_seller = Column(Boolean, default=False)
    tags = Column(JSON, nullable=True)  # list of tags
    # SEO
    meta_title = Column(String(200), nullable=True)
    meta_description = Column(Text, nullable=True)
    # Ratings aggregated
    avg_rating = Column(Float, default=0.0)
    review_count = Column(Integer, default=0)
    sold_count = Column(Integer, default=0)
    is_returnable = Column(Boolean, default=True, server_default="true")
    return_window_days = Column(Integer, default=7, server_default="7")

    # Difficulty Level
    difficulty_level = Column(
        String(20),
        nullable=True,
        comment="Skill level: beginner, intermediate, advanced"
    )

    # Gender Category
    gender = Column(
        String(10),
        nullable=True,
        comment="Gender classification: male, female, unisex, boys, girls"
    )

    # ── Catalog v2 — Amazon/Flipkart-style structured fields ────────────────
    highlights = Column(
        _JSON,
        nullable=True,
        default=list,
        server_default="[]",
        comment="Bullet-point product highlights; List[str]",
    )

    specifications = Column(
        _JSON,
        nullable=True,
        default=dict,
        server_default="{}",
        comment="Grouped product specifications; Dict[str, Dict[str, scalar]]",
    )

    manufacturer_info = Column(
        _JSON,
        nullable=True,
        default=dict,
        server_default="{}",
        comment="Manufacturer and compliance metadata; Dict[str, scalar]",
    )

    extra_data = Column(
        _JSON,
        nullable=True,
        default=dict,
        server_default="{}",
        comment="Extensible future metadata; Dict[str, Any]",
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ────────────────────────────────────────────────────────
    category = relationship("Category", back_populates="products")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    cart_items = relationship("CartItem", back_populates="product")
    wishlist_items = relationship("Wishlist", back_populates="product")
    order_items = relationship("OrderItem", back_populates="product")
    reviews = relationship("Review", back_populates="product")

    __table_args__ = (
        Index(
            "ix_products_specifications_gin",
            "specifications",
            postgresql_using="gin",
        ),
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(150), nullable=False)
    value = Column(String(150), nullable=False)
    sku = Column(String(150), unique=True, nullable=True)
    price_modifier = Column(Float, default=0.0)
    stock = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    product = relationship("Product", back_populates="variants")


class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    url = Column(String(500), nullable=False)
    public_id = Column(String(300), nullable=True)  # Cloudinary public_id
    alt_text = Column(String(300), nullable=True)
    is_primary = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)

    product = relationship("Product", back_populates="images")
