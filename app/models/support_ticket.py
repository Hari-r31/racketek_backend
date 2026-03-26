"""
Support Ticket and TicketReply models

Enum source: app.enums.TicketStatus, app.enums.TicketPriority,
             app.enums.TicketAuthorType  (do not redefine locally)
DB column:   String (VARCHAR) — no PostgreSQL native enum types.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from app.enums import TicketStatus, TicketPriority, TicketAuthorType  # noqa: F401 — re-exported


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id          = Column(Integer, primary_key=True, index=True)

    # Added safely via migration (nullable)
    ticket_number = Column(String(30), unique=True, nullable=True, index=True)
    image_urls    = Column(JSON, nullable=False, default=list)

    # Existing columns — DO NOT change types or names
    user_id       = Column(Integer, ForeignKey("users.id",   ondelete="CASCADE"),   nullable=False, index=True)
    order_id      = Column(Integer, ForeignKey("orders.id",  ondelete="SET NULL"),  nullable=True,  index=True)
    subject       = Column(String(300), nullable=False)
    message       = Column(Text, nullable=False)
    status        = Column(String(30),  default=TicketStatus.open)
    priority      = Column(String(10),  default=TicketPriority.medium)
    admin_reply   = Column(Text, nullable=True)
    resolved_at   = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user    = relationship("User",        back_populates="support_tickets")
    replies = relationship("TicketReply", back_populates="ticket",
                           cascade="all, delete-orphan",
                           order_by="TicketReply.created_at")


class TicketReply(Base):
    """
    Threaded conversation entries on a ticket.
    author_type: TicketAuthorType — "user" | "admin"
    """
    __tablename__ = "ticket_replies"

    id          = Column(Integer, primary_key=True, index=True)
    ticket_id   = Column(Integer, ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    author_type = Column(String(10), nullable=False)   # TicketAuthorType value
    message     = Column(Text, nullable=False)
    image_urls  = Column(JSON, nullable=False, default=list)
    created_at  = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("SupportTicket", back_populates="replies")
    user   = relationship("User")
