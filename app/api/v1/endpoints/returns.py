"""
Return request endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.dependencies import get_db, get_current_user, require_staff_or_admin
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.models.return_request import ReturnRequest, ReturnStatus
from app.schemas.return_request import ReturnCreate, ReturnAdminUpdate, ReturnResponse

router = APIRouter()


@router.get("", response_model=List[ReturnResponse])
def my_returns(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(ReturnRequest).filter(ReturnRequest.user_id == current_user.id).all()


@router.post("", response_model=ReturnResponse, status_code=201)
def request_return(
    payload: ReturnCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(
        Order.id == payload.order_id,
        Order.user_id == current_user.id,
        Order.status == OrderStatus.DELIVERED,
    ).first()
    if not order:
        raise HTTPException(status_code=400, detail="Order not found or not eligible for return")

    existing = db.query(ReturnRequest).filter(
        ReturnRequest.order_id == payload.order_id,
        ReturnRequest.user_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Return already requested for this order")

    rr = ReturnRequest(
        order_id=payload.order_id,
        user_id=current_user.id,
        reason=payload.reason,
    )
    db.add(rr)
    order.status = OrderStatus.RETURNED
    db.commit()
    db.refresh(rr)
    return rr


@router.get("/admin", response_model=List[ReturnResponse])
def admin_list_returns(
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    return db.query(ReturnRequest).order_by(ReturnRequest.created_at.desc()).all()


@router.put("/admin/{return_id}", response_model=ReturnResponse)
def admin_update_return(
    return_id: int,
    payload: ReturnAdminUpdate,
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    rr = db.query(ReturnRequest).filter(ReturnRequest.id == return_id).first()
    if not rr:
        raise HTTPException(status_code=404, detail="Return request not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(rr, field, value)
    db.commit()
    db.refresh(rr)
    return rr
