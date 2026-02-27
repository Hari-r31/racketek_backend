"""
Support Ticket schemas
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.support_ticket import TicketStatus, TicketPriority


class SupportTicketCreate(BaseModel):
    subject: str
    message: str
    order_id: Optional[int] = None
    priority: TicketPriority = TicketPriority.MEDIUM


class SupportTicketReply(BaseModel):
    admin_reply: str
    status: TicketStatus = TicketStatus.RESOLVED


class SupportTicketResponse(BaseModel):
    id: int
    user_id: int
    order_id: Optional[int]
    subject: str
    message: str
    status: TicketStatus
    priority: TicketPriority
    admin_reply: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
