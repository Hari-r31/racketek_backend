"""
Product, ProductVariant, and ProductImage models
"""
import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey,
    Text, Boolean, Enum as SAEnum, JSON
)
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class ProductStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    OUT_OF_STOCK = "out_of_stock"
    DRAFT = "draft"


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
    status = Column(SAEnum(ProductStatus), default=ProductStatus.ACTIVE)
    is_featured = Column(Boolean, default=False)
    is_best_seller = Column(Boolean, default=False)
    tags = Column(JSON, nullable=True)  # list of tags
    # SEO
    meta_title = Column(String(200), nullable=True)
    meta_description = Column(String(500), nullable=True)
    # Ratings aggregated
    avg_rating = Column(Float, default=0.0)
    review_count = Column(Integer, default=0)
    sold_count = Column(Integer, default=0)
    is_returnable = Column(Boolean, default=True, server_default="true")  # can be returned
    return_window_days = Column(Integer, default=7, server_default="7")   # days after delivery

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    category = relationship("Category", back_populates="products")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    cart_items = relationship("CartItem", back_populates="product")
    wishlist_items = relationship("Wishlist", back_populates="product")
    order_items = relationship("OrderItem", back_populates="product")
    reviews = relationship("Review", back_populates="product")


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(150), nullable=False)   # e.g. "Size", "Color", "Weight"
    value = Column(String(150), nullable=False)  # e.g. "XL", "Red", "85g"
    sku = Column(String(150), unique=True, nullable=True)
    price_modifier = Column(Float, default=0.0)  # add/subtract from base price
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
