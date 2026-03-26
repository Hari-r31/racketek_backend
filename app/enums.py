"""
app/enums.py — SINGLE SOURCE OF TRUTH for all application enums.

Rules enforced:
  • All values are lowercase snake_case strings.
  • All Enum keys match their values exactly (pending = "pending").
  • All Enum classes inherit from (str, enum.Enum) so they serialize
    directly as strings in JSON responses.
  • DO NOT define enums anywhere else in the codebase.
    Import from here: `from app.enums import OrderStatus`
"""

import enum


# ── Orders ────────────────────────────────────────────────────────────────────

class OrderStatus(str, enum.Enum):
    pending          = "pending"
    paid             = "paid"
    processing       = "processing"
    shipped          = "shipped"
    out_for_delivery = "out_for_delivery"
    delivered        = "delivered"
    cancelled        = "cancelled"
    returned         = "returned"
    refunded         = "refunded"


# ── Users ─────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    customer    = "customer"
    staff       = "staff"
    admin       = "admin"
    super_admin = "super_admin"


class AuthProvider(str, enum.Enum):
    local  = "local"
    google = "google"


# ── Payments ──────────────────────────────────────────────────────────────────

class PaymentMethod(str, enum.Enum):
    razorpay = "razorpay"
    cod      = "cod"


class PaymentStatus(str, enum.Enum):
    pending            = "pending"
    success            = "success"
    failed             = "failed"
    refunded           = "refunded"
    partially_refunded = "partially_refunded"


# ── Shipments ─────────────────────────────────────────────────────────────────

class ShipmentStatus(str, enum.Enum):
    pending          = "pending"
    picked_up        = "picked_up"
    in_transit       = "in_transit"
    out_for_delivery = "out_for_delivery"
    delivered        = "delivered"
    failed_delivery  = "failed_delivery"
    returned         = "returned"


# ── Returns ───────────────────────────────────────────────────────────────────

class ReturnStatus(str, enum.Enum):
    requested        = "requested"
    approved         = "approved"
    rejected         = "rejected"
    picked_up        = "picked_up"
    refund_initiated = "refund_initiated"
    completed        = "completed"


# ── Support Tickets ───────────────────────────────────────────────────────────

class TicketStatus(str, enum.Enum):
    open                 = "open"
    in_progress          = "in_progress"
    waiting_for_customer = "waiting_for_customer"
    resolved             = "resolved"
    closed               = "closed"


class TicketPriority(str, enum.Enum):
    low    = "low"
    medium = "medium"
    high   = "high"


class TicketAuthorType(str, enum.Enum):
    user  = "user"
    admin = "admin"


# ── Products ──────────────────────────────────────────────────────────────────

class ProductStatus(str, enum.Enum):
    active       = "active"
    inactive     = "inactive"
    out_of_stock = "out_of_stock"
    draft        = "draft"


class DifficultyLevel(str, enum.Enum):
    beginner     = "beginner"
    intermediate = "intermediate"
    advanced     = "advanced"


class GenderCategory(str, enum.Enum):
    male   = "male"
    female = "female"
    unisex = "unisex"
    boys   = "boys"
    girls  = "girls"


# ── Coupons ───────────────────────────────────────────────────────────────────

class DiscountType(str, enum.Enum):
    percentage = "percentage"
    fixed      = "fixed"


# ── Inventory ─────────────────────────────────────────────────────────────────

class ReservationStatus(str, enum.Enum):
    active    = "active"
    confirmed = "confirmed"
    released  = "released"


# ── Revenue / Analytics ───────────────────────────────────────────────────────

class RevenueLogType(str, enum.Enum):
    sale     = "sale"
    refund   = "refund"
    discount = "discount"
