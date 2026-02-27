"""
Product review endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import math

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.review import Review
from app.models.product import Product
from app.schemas.review import ReviewCreate, ReviewUpdate, ReviewResponse, PaginatedReviews

router = APIRouter()


@router.get("/{product_id}", response_model=PaginatedReviews)
def get_product_reviews(
    product_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    q = db.query(Review).filter(
        Review.product_id == product_id,
        Review.is_approved == True,
    ).order_by(Review.created_at.desc())

    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()
    avg = db.query(func.avg(Review.rating)).filter(
        Review.product_id == product_id,
        Review.is_approved == True,
    ).scalar() or 0.0

    return PaginatedReviews(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        avg_rating=round(float(avg), 2),
    )


@router.post("", response_model=ReviewResponse, status_code=201)
def create_review(
    payload: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.query(Review).filter(
        Review.product_id == payload.product_id,
        Review.user_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already reviewed this product")

    # Check if verified purchase
    from app.models.order import Order, OrderItem, OrderStatus
    is_verified = False
    if payload.order_id:
        order = db.query(Order).filter(
            Order.id == payload.order_id,
            Order.user_id == current_user.id,
            Order.status == OrderStatus.DELIVERED,
        ).first()
        if order:
            order_item = db.query(OrderItem).filter(
                OrderItem.order_id == order.id,
                OrderItem.product_id == payload.product_id,
            ).first()
            is_verified = order_item is not None

    review = Review(
        product_id=payload.product_id,
        user_id=current_user.id,
        order_id=payload.order_id,
        rating=payload.rating,
        title=payload.title,
        body=payload.body,
        is_verified_purchase=is_verified,
    )
    db.add(review)
    db.flush()

    # Update product avg rating
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if product:
        all_ratings = db.query(func.avg(Review.rating), func.count(Review.id)).filter(
            Review.product_id == payload.product_id,
            Review.is_approved == True,
        ).first()
        product.avg_rating = round(float(all_ratings[0] or 0), 2)
        product.review_count = all_ratings[1] or 0

    db.commit()
    db.refresh(review)
    return review


@router.delete("/{review_id}", status_code=204)
def delete_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review = db.query(Review).filter(
        Review.id == review_id,
        Review.user_id == current_user.id,
    ).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    db.delete(review)
    db.commit()
