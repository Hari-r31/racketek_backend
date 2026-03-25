"""
User model

Fixes applied
-------------
H3  — auth_provider column ("local" | "google").
H5  — email_marketing_consent + last_abandoned_cart_email_at columns.
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class UserRole(str, enum.Enum):
    CUSTOMER    = "CUSTOMER"
    STAFF       = "STAFF"
    ADMIN       = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    full_name       = Column(String(150), nullable=False)
    email           = Column(String(255), unique=True, index=True, nullable=False)
    phone           = Column(String(20),  nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role            = Column(SAEnum(UserRole), default=UserRole.CUSTOMER, nullable=False)
    is_active         = Column(Boolean, default=True)
    is_email_verified = Column(Boolean, default=False)
    profile_image   = Column(String(500), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # H3 FIX: "local" for email/password users, "google" for OAuth users.
    auth_provider = Column(
        String(20), nullable=False, server_default="local", default="local"
    )

    # H5 FIX: GDPR/CAN-SPAM compliant marketing emails
    email_marketing_consent     = Column(Boolean, default=False, nullable=False, server_default="false")
    last_abandoned_cart_email_at = Column(DateTime, nullable=True)

    # Extended profile fields
    date_of_birth = Column(String(20),  nullable=True)
    address_line1 = Column(String(300), nullable=True)
    city          = Column(String(100), nullable=True)
    state         = Column(String(100), nullable=True)
    pincode       = Column(String(10),  nullable=True)

    # ── Email OTP (verification + forgot-password) ────────────────────────
    email_otp          = Column(String(64),  nullable=True)
    email_otp_expiry   = Column(DateTime,    nullable=True)
    email_otp_attempts = Column(Integer,     nullable=True, default=0)
    email_otp_purpose  = Column(String(30),  nullable=True)

    # ── Reset OTP (separate slot for forgot-password) ─────────────────────
    reset_otp          = Column(String(64),  nullable=True)
    reset_otp_expiry   = Column(DateTime,    nullable=True)
    reset_otp_attempts = Column(Integer,     nullable=True, default=0)

    # ── Relationships ──────────────────────────────────────────────────────
    addresses       = relationship("Address",       back_populates="user", cascade="all, delete-orphan")
    cart            = relationship("Cart",          back_populates="user", uselist=False, cascade="all, delete-orphan")
    wishlist        = relationship("Wishlist",      back_populates="user", cascade="all, delete-orphan")
    orders          = relationship("Order",         back_populates="user")
    reviews         = relationship("Review",        back_populates="user")
    support_tickets = relationship("SupportTicket", back_populates="user")
