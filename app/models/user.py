"""
User model with role-based access and email-verification token storage
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class UserRole(str, enum.Enum):
    CUSTOMER   = "customer"
    STAFF      = "staff"
    ADMIN      = "admin"
    SUPER_ADMIN = "super_admin"


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    full_name       = Column(String(150), nullable=False)
    email           = Column(String(255), unique=True, index=True, nullable=False)
    phone           = Column(String(20),  nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role            = Column(SAEnum(UserRole), default=UserRole.CUSTOMER, nullable=False)
    is_active       = Column(Boolean, default=True)
    is_email_verified = Column(Boolean, default=False)
    profile_image   = Column(String(500), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Extended profile fields
    date_of_birth = Column(String(20),  nullable=True)   # ISO format: YYYY-MM-DD
    address_line1 = Column(String(300), nullable=True)
    city          = Column(String(100), nullable=True)
    state         = Column(String(100), nullable=True)
    pincode       = Column(String(10),  nullable=True)

    # Phone verification flag
    is_phone_verified = Column(Boolean, default=False)

    # Email OTP (hashed, 10-min expiry)
    email_otp        = Column(String(64), nullable=True)
    email_otp_expiry = Column(DateTime,   nullable=True)

    # Phone OTP (hashed, 10-min expiry)
    phone_otp        = Column(String(64), nullable=True)
    phone_otp_expiry = Column(DateTime,   nullable=True)

    # Password-reset OTP (hashed, 10-min expiry) — works for both email & phone
    reset_otp            = Column(String(64), nullable=True)
    reset_otp_expiry     = Column(DateTime,   nullable=True)
    reset_otp_contact    = Column(String(255), nullable=True)  # email or phone used

    # Legacy token-based verification (kept for backwards compat)
    email_verify_token        = Column(String(256), nullable=True)
    email_verify_token_expiry = Column(DateTime,    nullable=True)

    # Legacy password-reset token
    password_reset_token        = Column(String(256), nullable=True)
    password_reset_token_expiry = Column(DateTime,    nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────
    addresses      = relationship("Address",       back_populates="user", cascade="all, delete-orphan")
    cart           = relationship("Cart",          back_populates="user", uselist=False, cascade="all, delete-orphan")
    wishlist       = relationship("Wishlist",      back_populates="user", cascade="all, delete-orphan")
    orders         = relationship("Order",         back_populates="user")
    reviews        = relationship("Review",        back_populates="user")
    support_tickets = relationship("SupportTicket", back_populates="user")
