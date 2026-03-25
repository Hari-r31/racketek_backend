"""
Support ticket endpoints — production-grade
==========================================

ROUTE ORDER IS CRITICAL:
  FastAPI matches routes top-to-bottom. All /admin/* routes MUST be declared
  before /{ticket_id} routes, otherwise "admin" gets coerced to int → 422.

Customer routes:
  GET    /support                          list own tickets
  POST   /support                          create ticket
  GET    /support/{ticket_id}              get single ticket + replies
  POST   /support/{ticket_id}/reply        add a reply
  POST   /support/{ticket_id}/close        close ticket

Admin routes (declared first, before /{ticket_id}):
  GET    /support/admin                    paginated list
  GET    /support/admin/{ticket_id}        rich detail
  GET    /support/admin/{ticket_id}/customer-summary
  PUT    /support/admin/{ticket_id}/reply
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, case, or_
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_db, get_current_user, require_staff_or_admin
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentStatus
from app.models.return_request import ReturnRequest
from app.models.support_ticket import SupportTicket, TicketReply, TicketStatus, TicketPriority
from app.models.user import User
from app.schemas.support_ticket import (
    AdminReplyCreate,
    AdminTicketDetail,
    CustomerRiskSummary,
    OrderSummaryRow,
    SupportTicketCreate,
    SupportTicketResponse,
    TicketReplyResponse,
    UserReplyCreate,
)

router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# Shared helpers
# ══════════════════════════════════════════════════════════════════════════════

def _generate_ticket_number(db: Session) -> str:
    year   = datetime.utcnow().year
    prefix = f"TKT-{year}-"
    latest = (
        db.query(SupportTicket.ticket_number)
        .filter(SupportTicket.ticket_number.like(f"{prefix}%"))
        .order_by(SupportTicket.ticket_number.desc())
        .with_for_update()
        .first()
    )
    if latest and latest[0]:
        try:
            seq = int(latest[0].split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:06d}"


def _build_reply_response(reply: TicketReply) -> TicketReplyResponse:
    author_name = None
    if reply.user:
        author_name = reply.user.full_name
    elif reply.author_type == "admin":
        author_name = "Racketek Support"
    return TicketReplyResponse(
        id=reply.id,
        ticket_id=reply.ticket_id,
        user_id=reply.user_id,
        author_type=reply.author_type,
        message=reply.message,
        image_urls=reply.image_urls or [],
        created_at=reply.created_at,
        author_name=author_name,
    )


def _ticket_to_response(ticket: SupportTicket) -> SupportTicketResponse:
    replies = [_build_reply_response(r) for r in (ticket.replies or [])]
    return SupportTicketResponse(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        user_id=ticket.user_id,
        order_id=ticket.order_id,
        subject=ticket.subject,
        message=ticket.message,
        image_urls=ticket.image_urls or [],
        status=ticket.status,
        priority=ticket.priority,
        admin_reply=ticket.admin_reply,
        resolved_at=ticket.resolved_at,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        user=ticket.user,
        replies=replies,
    )


def _get_ticket_or_404(ticket_id: int, user_id: int, db: Session) -> SupportTicket:
    ticket = (
        db.query(SupportTicket)
        .options(joinedload(SupportTicket.replies).joinedload(TicketReply.user))
        .filter(SupportTicket.id == ticket_id, SupportTicket.user_id == user_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def _get_customer_summary_direct(uid: int, db: Session) -> CustomerRiskSummary:
    result = (
        db.query(
            User.id,
            User.full_name,
            User.email,
            User.phone,
            User.created_at.label("member_since"),
            func.count(func.distinct(Order.id)).label("total_orders"),
            func.count(func.distinct(
                case((Order.status == OrderStatus.CANCELLED, Order.id), else_=None)
            )).label("total_cancellations"),
            func.count(func.distinct(ReturnRequest.id)).label("total_returns"),
            func.count(func.distinct(
                case((Payment.status == PaymentStatus.REFUNDED, Payment.id), else_=None)
            )).label("total_refunds"),
            func.coalesce(
                func.sum(
                    case(
                        (Order.status.not_in([
                            OrderStatus.CANCELLED,
                            OrderStatus.RETURNED,
                            OrderStatus.REFUNDED,
                        ]), Order.total_amount),
                        else_=0,
                    )
                ),
                0.0,
            ).label("lifetime_value"),
            func.max(Order.created_at).label("last_order_date"),
        )
        .outerjoin(Order,         Order.user_id == User.id)
        .outerjoin(ReturnRequest, ReturnRequest.user_id == User.id)
        .outerjoin(Payment,       Payment.order_id == Order.id)
        .filter(User.id == uid)
        .group_by(User.id, User.full_name, User.email, User.phone, User.created_at)
        .first()
    )

    if not result:
        raise HTTPException(status_code=404, detail="User not found")

    (
        user_id, full_name, email, phone, member_since,
        total_orders, total_cancellations, total_returns, total_refunds,
        lifetime_value, last_order_date,
    ) = result

    risk_tier, risk_reason = _compute_risk(
        total_orders, total_cancellations, total_returns, total_refunds
    )
    return CustomerRiskSummary(
        user_id=user_id,
        full_name=full_name,
        email=email,
        phone=phone,
        member_since=member_since,
        total_orders=total_orders,
        total_cancellations=total_cancellations,
        total_returns=total_returns,
        total_refunds=total_refunds,
        lifetime_value=float(lifetime_value or 0),
        last_order_date=last_order_date,
        risk_tier=risk_tier,
        risk_reason=risk_reason,
    )


def _compute_risk(total_orders, total_cancellations, total_returns, total_refunds):
    if total_orders == 0:
        return "low", "No orders placed yet"
    cancel_rate = total_cancellations / total_orders
    return_rate = total_returns / total_orders
    if cancel_rate >= 0.5 or return_rate >= 0.4 or total_refunds >= 3:
        reasons = []
        if cancel_rate >= 0.5: reasons.append(f"{int(cancel_rate*100)}% cancellation rate")
        if return_rate >= 0.4:  reasons.append(f"{int(return_rate*100)}% return rate")
        if total_refunds >= 3:  reasons.append(f"{total_refunds} refunds")
        return "high", "; ".join(reasons)
    if cancel_rate >= 0.25 or return_rate >= 0.2 or total_refunds >= 1:
        reasons = []
        if cancel_rate >= 0.25: reasons.append(f"{int(cancel_rate*100)}% cancellation rate")
        if return_rate >= 0.2:  reasons.append(f"{int(return_rate*100)}% return rate")
        if total_refunds >= 1:  reasons.append(f"{total_refunds} refund(s)")
        return "medium", "; ".join(reasons)
    return "low", "Good order history"


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES — declared BEFORE /{ticket_id} to avoid 422
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/admin")
def admin_list_tickets(
    page:     int           = Query(1, ge=1),
    per_page: int           = Query(20, ge=1, le=500),
    status:   Optional[str] = None,
    priority: Optional[str] = None,
    search:   Optional[str] = None,
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    q = (
        db.query(SupportTicket)
        .options(joinedload(SupportTicket.user))
        .options(joinedload(SupportTicket.replies))
    )

    if status:
        try:
            q = q.filter(SupportTicket.status == TicketStatus(status))
        except ValueError:
            pass

    if priority:
        try:
            q = q.filter(SupportTicket.priority == TicketPriority(priority))
        except ValueError:
            pass

    if search:
        q = q.outerjoin(User, SupportTicket.user_id == User.id).filter(
            or_(
                SupportTicket.ticket_number.ilike(f"%{search}%"),
                SupportTicket.subject.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
            )
        )

    total = q.count()
    tickets = (
        q.order_by(SupportTicket.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "items":       [_ticket_to_response(t) for t in tickets],
        "total":       total,
        "page":        page,
        "per_page":    per_page,
        "total_pages": math.ceil(total / per_page) if per_page else 1,
    }


@router.get("/admin/{ticket_id}/customer-summary", response_model=CustomerRiskSummary)
def admin_customer_summary(
    ticket_id: int,
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _get_customer_summary_direct(ticket.user_id, db)


@router.get("/admin/{ticket_id}", response_model=AdminTicketDetail)
def admin_get_ticket_detail(
    ticket_id: int,
    _: User = Depends(require_staff_or_admin),
    db: Session = Depends(get_db),
):
    ticket = (
        db.query(SupportTicket)
        .options(
            joinedload(SupportTicket.user),
            joinedload(SupportTicket.replies).joinedload(TicketReply.user),
        )
        .filter(SupportTicket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    customer_summary = _get_customer_summary_direct(ticket.user_id, db)

    orders = (
        db.query(Order)
        .filter(Order.user_id == ticket.user_id)
        .order_by(Order.created_at.desc())
        .limit(20)
        .all()
    )
    order_history = [
        OrderSummaryRow(
            id=o.id,
            order_number=o.order_number,
            status=o.status.value,
            total_amount=o.total_amount,
            created_at=o.created_at,
        )
        for o in orders
    ]

    return AdminTicketDetail(
        ticket=_ticket_to_response(ticket),
        customer_summary=customer_summary,
        order_history=order_history,
    )


@router.put("/admin/{ticket_id}/reply", response_model=SupportTicketResponse)
def admin_reply_ticket(
    ticket_id: int,
    payload:   AdminReplyCreate,
    admin:     User = Depends(require_staff_or_admin),
    db:        Session = Depends(get_db),
):
    ticket = (
        db.query(SupportTicket)
        .options(
            joinedload(SupportTicket.user),
            joinedload(SupportTicket.replies).joinedload(TicketReply.user),
        )
        .filter(SupportTicket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    reply = TicketReply(
        ticket_id=ticket.id,
        user_id=admin.id,
        author_type="admin",
        message=payload.message,
        image_urls=payload.image_urls,
    )
    db.add(reply)

    ticket.admin_reply = payload.message
    ticket.status      = payload.status
    if payload.priority:
        ticket.priority = payload.priority
    if payload.status == TicketStatus.RESOLVED and not ticket.resolved_at:
        ticket.resolved_at = datetime.utcnow()
    ticket.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(ticket)
    return _ticket_to_response(ticket)


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOMER ROUTES — declared AFTER /admin/* to avoid shadowing
# ══════════════════════════════════════════════════════════════════════════════

@router.get("", response_model=List[SupportTicketResponse])
def my_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tickets = (
        db.query(SupportTicket)
        .options(joinedload(SupportTicket.replies).joinedload(TicketReply.user))
        .filter(SupportTicket.user_id == current_user.id)
        .order_by(SupportTicket.created_at.desc())
        .all()
    )
    return [_ticket_to_response(t) for t in tickets]


@router.post("", response_model=SupportTicketResponse, status_code=201)
def create_ticket(
    payload: SupportTicketCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket_number = _generate_ticket_number(db)
    ticket = SupportTicket(
        user_id=current_user.id,
        order_id=payload.order_id,
        subject=payload.subject,
        message=payload.message,
        priority=payload.priority,
        image_urls=payload.image_urls,
        ticket_number=ticket_number,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return _ticket_to_response(ticket)


@router.get("/{ticket_id}", response_model=SupportTicketResponse)
def get_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _ticket_to_response(
        _get_ticket_or_404(ticket_id, current_user.id, db)
    )


@router.post("/{ticket_id}/reply", response_model=SupportTicketResponse)
def user_reply(
    ticket_id: int,
    payload: UserReplyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = _get_ticket_or_404(ticket_id, current_user.id, db)
    if ticket.status == TicketStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Cannot reply to a closed ticket")

    reply = TicketReply(
        ticket_id=ticket.id,
        user_id=current_user.id,
        author_type="user",
        message=payload.message,
        image_urls=payload.image_urls,
    )
    db.add(reply)

    if ticket.status == TicketStatus.WAITING_FOR_CUSTOMER:
        ticket.status = TicketStatus.IN_PROGRESS
    ticket.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(ticket)
    return _ticket_to_response(ticket)


@router.post("/{ticket_id}/close", response_model=SupportTicketResponse)
def user_close_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = _get_ticket_or_404(ticket_id, current_user.id, db)
    if ticket.status == TicketStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Ticket is already closed")

    ticket.status     = TicketStatus.CLOSED
    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)
    return _ticket_to_response(ticket)
