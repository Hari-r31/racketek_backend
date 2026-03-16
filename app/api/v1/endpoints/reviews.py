"""
Product review endpoints
Rules:
- Only users who have a DELIVERED order containing this product can submit a review.
- GET response includes user_has_purchased + user_has_reviewed flags for the frontend.
- rating_breakdown returned for the star distribution bars.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from app.core.dependencies import get_db, get_current_user
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.user import User
from app.models.review import Review
from app.models.product import Product
from app.models.order import Order, OrderItem, OrderStatus
from app.schemas.review import ReviewCreate, ReviewUpdate, ReviewResponse, PaginatedReviews

router = APIRouter()

# Optional bearer — does not raise 401 when missing (lets guests read reviews)
_optional_bearer = HTTPBearer(auto_error=False)


def _get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Return the current user if a valid token is present, else None."""
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return db.query(User).filter(User.id == int(user_id), User.is_active == True).first()


def _has_purchased(db: Session, user_id: int, product_id: int) -> bool:
    """Return True if the user has at least one DELIVERED order containing this product."""
    return (
        db.query(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(
            Order.user_id == user_id,
            Order.status == OrderStatus.DELIVERED,
            OrderItem.product_id == product_id,
        )
        .first()
    ) is not None


# ── GET reviews ───────────────────────────────────────────────────────────────
@router.get("/{product_id}", response_model=PaginatedReviews)
def get_product_reviews(
    product_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(_get_optional_user),
):
    q = (
        db.query(Review)
        .filter(Review.product_id == product_id, Review.is_approved == True)
        .order_by(Review.created_at.desc())
    )
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()

    avg = (
        db.query(func.avg(Review.rating))
        .filter(Review.product_id == product_id, Review.is_approved == True)
        .scalar()
    ) or 0.0

    # Star breakdown
    breakdown_rows = (
        db.query(Review.rating, func.count(Review.id))
        .filter(Review.product_id == product_id, Review.is_approved == True)
        .group_by(Review.rating)
        .all()
    )
    rating_breakdown: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for rating_val, count in breakdown_rows:
        star = int(round(rating_val))
        if 1 <= star <= 5:
            rating_breakdown[star] += count

    # Per-user flags (only meaningful when logged in)
    user_has_purchased = False
    user_has_reviewed = False
    if current_user:
        user_has_purchased = _has_purchased(db, current_user.id, product_id)
        user_has_reviewed = (
            db.query(Review)
            .filter(Review.product_id == product_id, Review.user_id == current_user.id)
            .first()
        ) is not None

    return PaginatedReviews(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        avg_rating=round(float(avg), 2),
        rating_breakdown=rating_breakdown,
        user_has_purchased=user_has_purchased,
        user_has_reviewed=user_has_reviewed,
    )


# ── POST review ───────────────────────────────────────────────────────────────
@router.post("", response_model=ReviewResponse, status_code=201)
def create_review(
    payload: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Product must exist
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # ── PURCHASE GATE — only buyers can review ────────────────────────
    if not _has_purchased(db, current_user.id, payload.product_id):
        raise HTTPException(
            status_code=403,
            detail="Only customers who have purchased and received this product can leave a review.",
        )

    # One review per user per product
    existing = db.query(Review).filter(
        Review.product_id == payload.product_id,
        Review.user_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already reviewed this product.")

    # All purchases are verified (we already confirmed delivery above)
    review = Review(
        product_id=payload.product_id,
        user_id=current_user.id,
        order_id=payload.order_id,
        rating=payload.rating,
        title=payload.title,
        body=payload.body,
        is_verified_purchase=True,   # always true — purchase gate ensures it
    )
    db.add(review)
    db.flush()

    # Recompute aggregates
    agg = db.query(func.avg(Review.rating), func.count(Review.id)).filter(
        Review.product_id == payload.product_id,
        Review.is_approved == True,
    ).first()
    product.avg_rating = round(float(agg[0] or 0), 2)
    product.review_count = agg[1] or 0

    db.commit()
    db.refresh(review)
    return review


# ── DELETE review ─────────────────────────────────────────────────────────────
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
