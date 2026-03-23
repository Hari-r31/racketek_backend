"""
User model

Phone number is kept as optional profile/contact data only.
It plays NO role in authentication or OTP flows.

OTP columns (email-only):
  email_otp             — SHA-256 hash of the current active OTP
  email_otp_expiry      — expiry timestamp (5 minutes from issue)
  email_otp_attempts    — failed attempt count; locked after OTP_MAX_ATTEMPTS
  email_otp_purpose     — "verification" | "forgot_password" | "email_change"

Reset OTP columns (forgot-password flow):
  reset_otp             — SHA-256 hash
  reset_otp_expiry      — expiry timestamp
  reset_otp_attempts    — failed attempt count

All removed:
  - phone_otp / phone_otp_expiry        (SMS OTP — deleted)
  - is_phone_verified                   (no phone auth)
  - reset_otp_contact                   (was email OR phone — now email only)
  - email_verify_token / expiry         (legacy link-based flow — deleted)
  - password_reset_token / expiry       (legacy token flow — deleted)
"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class UserRole(str, enum.Enum):
    CUSTOMER    = "customer"
    STAFF       = "staff"
    ADMIN       = "admin"
    SUPER_ADMIN = "super_admin"


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    full_name       = Column(String(150), nullable=False)
    email           = Column(String(255), unique=True, index=True, nullable=False)
    phone           = Column(String(20),  nullable=True)   # profile/contact only
    hashed_password = Column(String(255), nullable=False)
    role            = Column(SAEnum(UserRole), default=UserRole.CUSTOMER, nullable=False)
    is_active         = Column(Boolean, default=True)
    is_email_verified = Column(Boolean, default=False)
    profile_image   = Column(String(500), nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Extended profile fields
    date_of_birth = Column(String(20),  nullable=True)   # ISO: YYYY-MM-DD
    address_line1 = Column(String(300), nullable=True)
    city          = Column(String(100), nullable=True)
    state         = Column(String(100), nullable=True)
    pincode       = Column(String(10),  nullable=True)

    # ── Email OTP (verification + forgot-password) ────────────────────────
    # Shared OTP slot; purpose field determines the context.
    email_otp          = Column(String(64),  nullable=True)
    email_otp_expiry   = Column(DateTime,    nullable=True)
    email_otp_attempts = Column(Integer,     nullable=True, default=0)
    email_otp_purpose  = Column(String(30),  nullable=True)  # verification|forgot_password

    # ── Reset OTP (separate slot for forgot-password, belt-and-suspenders) ─
    # Using a dedicated slot keeps the forgot-password flow independent from
    # the email-verification flow so they cannot interfere with each other.
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
