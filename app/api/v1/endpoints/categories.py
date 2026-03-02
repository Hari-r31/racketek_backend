"""
Category endpoints — public read + admin write
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.dependencies import get_db, require_admin
from app.models.user import User
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse

router = APIRouter()


@router.get("", response_model=List[CategoryResponse])
def list_categories(
    parent_only: bool = Query(False, description="Only return root-level categories"),
    parent_id:   Optional[int] = Query(None, description="Return sub-categories of this parent ID"),
    db: Session = Depends(get_db),
):
    """
    Flexible category listing:
    - No params            → root categories with children nested
    - ?parent_only=true    → root categories only (flat)
    - ?parent_id=5         → sub-categories of category 5
    """
    q = db.query(Category).filter(Category.is_active == True)
    if parent_id is not None:
        q = q.filter(Category.parent_id == parent_id)
    else:
        q = q.filter(Category.parent_id == None)
    return q.order_by(Category.sort_order.asc(), Category.name.asc()).all()


@router.get("/all", response_model=List[CategoryResponse])
def list_all_categories(db: Session = Depends(get_db)):
    """Flat list of all active categories."""
    return (
        db.query(Category)
        .filter(Category.is_active == True)
        .order_by(Category.parent_id.asc().nullsfirst(), Category.sort_order.asc())
        .all()
    )


@router.get("/{slug}", response_model=CategoryResponse)
def get_category(slug: str, db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.slug == slug).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat


@router.post("", response_model=CategoryResponse, status_code=201)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if db.query(Category).filter(Category.slug == payload.slug).first():
        raise HTTPException(status_code=400, detail="Slug already exists")
    cat = Category(**payload.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.put("/{cat_id}", response_model=CategoryResponse)
def update_category(
    cat_id: int,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(cat, field, value)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/{cat_id}", status_code=204)
def delete_category(
    cat_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(cat)
    db.commit()
