"""
Support ticket endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.core.dependencies import get_db, get_current_user, require_staff_or_admin
from app.models.user import User
from app.models.support_ticket import SupportTicket, TicketStatus
from app.schemas.support_ticket import (
    SupportTicketCreate, SupportTicketReply, SupportTicketResponse
)

router = APIRouter()


@router.get("", response_model=List[SupportTicketResponse])
def my_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(SupportTicket).filter(
        SupportTicket.user_id == current_user.id
    ).order_by(SupportTicket.created_at.desc()).all()


@router.post("", response_model=SupportTicketResponse, status_code=201)
def create_ticket(
    payload: SupportTicketCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = SupportTicket(
        user_id=current_user.id,
        order_id=payload.order_id,
        subject=payload.subject,
        message=payload.message,
        priority=payload.priority,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/admin", response_model=List[SupportTicketResponse])
def admin_list_tickets(
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    return db.query(SupportTicket).order_by(SupportTicket.created_at.desc()).all()


@router.put("/admin/{ticket_id}/reply", response_model=SupportTicketResponse)
def reply_to_ticket(
    ticket_id: int,
    payload: SupportTicketReply,
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.admin_reply = payload.admin_reply
    ticket.status = payload.status
    if payload.status == TicketStatus.RESOLVED:
        ticket.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)
    return ticket
