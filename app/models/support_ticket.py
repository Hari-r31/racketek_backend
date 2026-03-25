"""
Support Ticket and TicketReply models — production-grade version.

SAFE MIGRATION NOTES:
  * ticket_number added as nullable then backfilled — no row breaks
  * image_urls added as JSON with empty-list default
  * waiting_for_customer status added to enum
  * TicketReply is a brand-new table — no existing data affected
  * Original columns (subject, message, admin_reply, etc.) are UNCHANGED
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SAEnum, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class TicketStatus(str, enum.Enum):
    OPEN                 = "OPEN"
    IN_PROGRESS          = "IN_PROGRESS"
    WAITING_FOR_CUSTOMER = "WAITING_FOR_CUSTOMER"
    RESOLVED             = "RESOLVED"
    CLOSED               = "CLOSED"


class TicketPriority(str, enum.Enum):
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id          = Column(Integer, primary_key=True, index=True)

    # ── New production columns (added safely via migration) ──────────────
    ticket_number = Column(String(30), unique=True, nullable=True, index=True)
    image_urls    = Column(JSON, nullable=False, default=list)

    # ── Existing columns — DO NOT change types or names ──────────────────
    user_id       = Column(Integer, ForeignKey("users.id",   ondelete="CASCADE"),   nullable=False, index=True)
    order_id      = Column(Integer, ForeignKey("orders.id",  ondelete="SET NULL"),  nullable=True,  index=True)
    subject       = Column(String(300), nullable=False)
    message       = Column(Text, nullable=False)
    status        = Column(SAEnum(TicketStatus),   default=TicketStatus.OPEN)
    priority      = Column(SAEnum(TicketPriority), default=TicketPriority.MEDIUM)
    admin_reply   = Column(Text, nullable=True)
    resolved_at   = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ────────────────────────────────────────────────────
    user    = relationship("User",        back_populates="support_tickets")
    replies = relationship("TicketReply", back_populates="ticket",
                           cascade="all, delete-orphan",
                           order_by="TicketReply.created_at")


class TicketReply(Base):
    """
    Threaded conversation entries on a ticket.
    author_type = "user" | "admin"
    """
    __tablename__ = "ticket_replies"

    id          = Column(Integer, primary_key=True, index=True)
    ticket_id   = Column(Integer, ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    author_type = Column(String(10), nullable=False)   # "user" or "admin"
    message     = Column(Text, nullable=False)
    image_urls  = Column(JSON, nullable=False, default=list)
    created_at  = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("SupportTicket", back_populates="replies")
    user   = relationship("User")
