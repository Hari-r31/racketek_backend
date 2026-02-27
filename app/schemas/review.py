"""
Review schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ReviewCreate(BaseModel):
    product_id: int
    order_id: Optional[int] = None
    rating: float = Field(..., ge=1.0, le=5.0)
    title: Optional[str] = None
    body: Optional[str] = None


class ReviewUpdate(BaseModel):
    rating: Optional[float] = Field(None, ge=1.0, le=5.0)
    title: Optional[str] = None
    body: Optional[str] = None


class ReviewResponse(BaseModel):
    id: int
    product_id: int
    user_id: int
    rating: float
    title: Optional[str]
    body: Optional[str]
    is_verified_purchase: bool
    is_approved: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedReviews(BaseModel):
    items: List[ReviewResponse]
    total: int
    page: int
    per_page: int
    avg_rating: float
