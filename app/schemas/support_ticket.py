"""
Support Ticket schemas — production-grade

Enum source: app.enums.TicketStatus, app.enums.TicketPriority  (do not redefine locally)
"""
from __future__ import annotations
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime
from app.enums import TicketStatus, TicketPriority


# ── Create / Update ───────────────────────────────────────────────────────────

class SupportTicketCreate(BaseModel):
    subject:    str              = Field(..., min_length=5, max_length=300)
    message:    str              = Field(..., min_length=10)
    order_id:   Optional[int]   = None
    priority:   TicketPriority  = TicketPriority.medium
    image_urls: List[str]        = Field(default_factory=list)

    @validator("image_urls")
    def max_five_images(cls, v):
        if len(v) > 5:
            raise ValueError("Maximum 5 images allowed per ticket")
        return v


class SupportTicketReply(BaseModel):
    admin_reply: Optional[str]  = None
    status:      TicketStatus   = TicketStatus.resolved


# ── User reply ────────────────────────────────────────────────────────────────

class UserReplyCreate(BaseModel):
    message:    str       = Field(..., min_length=1)
    image_urls: List[str] = Field(default_factory=list)

    @validator("image_urls")
    def max_five_images(cls, v):
        if len(v) > 5:
            raise ValueError("Maximum 5 images allowed per reply")
        return v


# ── Admin reply ───────────────────────────────────────────────────────────────

class AdminReplyCreate(BaseModel):
    message:    str              = Field(..., min_length=1)
    status:     TicketStatus    = TicketStatus.in_progress
    priority:   Optional[TicketPriority] = None
    image_urls: List[str]        = Field(default_factory=list)


# ── Response ──────────────────────────────────────────────────────────────────

class TicketReplyResponse(BaseModel):
    id:          int
    ticket_id:   int
    user_id:     Optional[int]
    author_type: str            # "user" | "admin"
    message:     str
    image_urls:  List[str]
    created_at:  datetime
    author_name: Optional[str] = None   # hydrated by endpoint

    class Config:
        from_attributes = True


class TicketUserInfo(BaseModel):
    id:        int
    full_name: str
    email:     str
    phone:     Optional[str] = None

    class Config:
        from_attributes = True


class SupportTicketResponse(BaseModel):
    id:            int
    ticket_number: Optional[str]
    user_id:       int
    order_id:      Optional[int]
    subject:       str
    message:       str
    image_urls:    List[str]      = []
    status:        TicketStatus
    priority:      TicketPriority
    admin_reply:   Optional[str]
    resolved_at:   Optional[datetime]
    created_at:    datetime
    updated_at:    datetime
    user:          Optional[TicketUserInfo] = None
    replies:       List[TicketReplyResponse] = []

    class Config:
        from_attributes = True


# ── Customer risk summary (admin) ─────────────────────────────────────────────

class CustomerRiskSummary(BaseModel):
    user_id:             int
    full_name:           str
    email:               str
    phone:               Optional[str]
    member_since:        datetime
    total_orders:        int
    total_cancellations: int
    total_returns:       int
    total_refunds:       int
    lifetime_value:      float
    last_order_date:     Optional[datetime]
    # Computed risk tier — always lowercase: "low" | "medium" | "high"
    risk_tier:           str
    risk_reason:         str


# ── Admin ticket detail (rich) ────────────────────────────────────────────────

class OrderSummaryRow(BaseModel):
    id:           int
    order_number: str
    status:       str
    total_amount: float
    created_at:   datetime

    class Config:
        from_attributes = True


class AdminTicketDetail(BaseModel):
    ticket:           SupportTicketResponse
    customer_summary: CustomerRiskSummary
    order_history:    List[OrderSummaryRow]

    class Config:
        from_attributes = True
