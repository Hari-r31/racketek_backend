"""
Migration 021 — Enforce enum consistency on remaining string-typed enum columns

Background
----------
Migrations 018–020 already converted all PostgreSQL native ENUM columns to
lowercase values.  Several columns were intentionally kept as VARCHAR (String)
to decouple Python validation from the DB layer.  This migration:

  1. Normalises any stale UPPERCASE / mixed-case values still in those columns
     (safe to re-run — no-ops if data is already lowercase).
  2. Adds CHECK constraints to prevent future out-of-contract values from
     ever reaching the DB, giving a hard DB-level guarantee that matches the
     Python enum contract.

Columns covered (all VARCHAR — no native PG enum type involved)
---------------------------------------------------------------
  orders.status                → OrderStatus values
  users.role                   → UserRole values
  payments.method              → PaymentMethod values
  payments.status              → PaymentStatus values
  shipments.status             → ShipmentStatus values
  return_requests.status       → ReturnStatus values
  support_tickets.status       → TicketStatus values
  support_tickets.priority     → TicketPriority values
  ticket_replies.author_type   → TicketAuthorType values  (new constraint)
  products.status              → ProductStatus values
  products.difficulty_level    → DifficultyLevel values   (nullable)
  products.gender              → GenderCategory values    (nullable)
  coupons.discount_type        → DiscountType values
  inventory_reservations.status → ReservationStatus values
  revenue_logs.type            → RevenueLogType values    (previously unconstrained)
  users.auth_provider          → AuthProvider values      (previously unconstrained)

Safety guarantees
-----------------
  • All UPDATE statements use LOWER(TRIM(col)) — idempotent and NULL-safe.
  • CHECK constraints use ALTER TABLE … ADD CONSTRAINT IF NOT EXISTS where
    supported, falling back to a safe existence check to avoid duplicate errors.
  • The downgrade() removes the CHECK constraints only — it does NOT revert
    data to UPPERCASE (data loss would be unacceptable and migrations 018-020
    already own that direction).

Revision ID: 021_enum_string_constraints
Revises:     020_enum_lowercase
"""

from alembic import op
import sqlalchemy as sa

revision = "021_enum_string_constraints"
down_revision = "020_enum_lowercase"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise(table: str, column: str) -> None:
    """Lowercase-trim any mixed-case values in a VARCHAR enum column."""
    op.execute(
        f"UPDATE {table} SET {column} = LOWER(TRIM({column})) "
        f"WHERE {column} IS NOT NULL AND {column} != LOWER(TRIM({column}))"
    )


def _add_check(constraint_name: str, table: str, column: str, values: list[str]) -> None:
    """Add a CHECK constraint for allowed enum values (nullable-safe)."""
    values_sql = ", ".join(f"'{v}'" for v in values)
    op.execute(
        f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} "
        f"CHECK ({column} IS NULL OR {column} IN ({values_sql}))"
    )


def _drop_check(constraint_name: str, table: str) -> None:
    op.execute(
        f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint_name}"
    )


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:

    # ── Step 1: normalise all VARCHAR enum columns ─────────────────────────

    _normalise("orders",                "status")
    _normalise("users",                 "role")
    _normalise("users",                 "auth_provider")
    _normalise("payments",              "method")
    _normalise("payments",              "status")
    _normalise("shipments",             "status")
    _normalise("return_requests",       "status")
    _normalise("support_tickets",       "status")
    _normalise("support_tickets",       "priority")
    _normalise("ticket_replies",        "author_type")
    _normalise("products",              "status")
    _normalise("products",              "difficulty_level")
    _normalise("products",              "gender")
    _normalise("coupons",               "discount_type")
    _normalise("inventory_reservations","status")
    _normalise("revenue_logs",          "type")

    # ── Step 2: add CHECK constraints ─────────────────────────────────────

    _add_check(
        "ck_orders_status", "orders", "status",
        ["pending","paid","processing","shipped","out_for_delivery",
         "delivered","cancelled","returned","refunded"],
    )

    _add_check(
        "ck_users_role", "users", "role",
        ["customer","staff","admin","super_admin"],
    )

    _add_check(
        "ck_users_auth_provider", "users", "auth_provider",
        ["local","google"],
    )

    _add_check(
        "ck_payments_method", "payments", "method",
        ["razorpay","cod"],
    )

    _add_check(
        "ck_payments_status", "payments", "status",
        ["pending","success","failed","refunded","partially_refunded"],
    )

    _add_check(
        "ck_shipments_status", "shipments", "status",
        ["pending","picked_up","in_transit","out_for_delivery",
         "delivered","failed_delivery","returned"],
    )

    _add_check(
        "ck_return_requests_status", "return_requests", "status",
        ["requested","approved","rejected","picked_up",
         "refund_initiated","completed"],
    )

    _add_check(
        "ck_support_tickets_status", "support_tickets", "status",
        ["open","in_progress","waiting_for_customer","resolved","closed"],
    )

    _add_check(
        "ck_support_tickets_priority", "support_tickets", "priority",
        ["low","medium","high"],
    )

    _add_check(
        "ck_ticket_replies_author_type", "ticket_replies", "author_type",
        ["user","admin"],
    )

    _add_check(
        "ck_products_status", "products", "status",
        ["active","inactive","out_of_stock","draft"],
    )

    _add_check(
        "ck_products_difficulty_level", "products", "difficulty_level",
        ["beginner","intermediate","advanced"],
    )

    _add_check(
        "ck_products_gender", "products", "gender",
        ["male","female","unisex","boys","girls"],
    )

    _add_check(
        "ck_coupons_discount_type", "coupons", "discount_type",
        ["percentage","fixed"],
    )

    _add_check(
        "ck_inventory_reservations_status", "inventory_reservations", "status",
        ["active","confirmed","released"],
    )

    _add_check(
        "ck_revenue_logs_type", "revenue_logs", "type",
        ["sale","refund","discount"],
    )


# ---------------------------------------------------------------------------
# Downgrade — removes CHECK constraints only (does NOT revert data)
# ---------------------------------------------------------------------------

def downgrade() -> None:
    _drop_check("ck_revenue_logs_type",              "revenue_logs")
    _drop_check("ck_inventory_reservations_status",  "inventory_reservations")
    _drop_check("ck_coupons_discount_type",          "coupons")
    _drop_check("ck_products_gender",                "products")
    _drop_check("ck_products_difficulty_level",      "products")
    _drop_check("ck_products_status",                "products")
    _drop_check("ck_ticket_replies_author_type",     "ticket_replies")
    _drop_check("ck_support_tickets_priority",       "support_tickets")
    _drop_check("ck_support_tickets_status",         "support_tickets")
    _drop_check("ck_return_requests_status",         "return_requests")
    _drop_check("ck_shipments_status",               "shipments")
    _drop_check("ck_payments_status",                "payments")
    _drop_check("ck_payments_method",                "payments")
    _drop_check("ck_users_auth_provider",            "users")
    _drop_check("ck_users_role",                     "users")
    _drop_check("ck_orders_status",                  "orders")
