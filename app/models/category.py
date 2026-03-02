"""
Category model with nested (parent-child) support
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Category(Base):
    __tablename__ = "categories"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(150), nullable=False)
    slug        = Column(String(200), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    image       = Column(String(500), nullable=True)
    parent_id   = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    is_active   = Column(Boolean, default=True)
    sort_order  = Column(Integer, default=0)          # ← for ordering parent + child cats
    # SEO
    meta_title       = Column(String(200), nullable=True)
    meta_description = Column(String(500), nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    # Self-referential
    parent   = relationship("Category", remote_side=[id], back_populates="children")
    children = relationship(
        "Category",
        back_populates="parent",
        order_by="Category.sort_order",          # children always sorted
    )
    products = relationship("Product", back_populates="category")
