"""
Review schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
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


class ReviewUserResponse(BaseModel):
    id: int
    full_name: str

    class Config:
        from_attributes = True


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
    user: Optional[ReviewUserResponse] = None

    class Config:
        from_attributes = True


class PaginatedReviews(BaseModel):
    items: List[ReviewResponse]
    total: int
    page: int
    per_page: int
    avg_rating: float
    rating_breakdown: Dict[int, int] = Field(
        default_factory=lambda: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    )
    # Per-viewer flags — False when request is unauthenticated
    user_has_purchased: bool = False
    user_has_reviewed: bool = False
