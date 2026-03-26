"""
Migration 021 — Enforce enum consistency: CHECK constraints + VARCHAR normalisation

Background
----------
Migrations 018–020 already converted all PostgreSQL native ENUM columns to
lowercase values using ALTER COLUMN ... USING LOWER(col::text)::new_enum.
Those columns are clean — no normalisation needed here.

This migration handles the remaining gaps:

  1. Normalises three VARCHAR columns that were NEVER touched by 018–020
     and have no native ENUM type:
       - users.auth_provider          ("local" | "google")
       - ticket_replies.author_type   ("user"  | "admin")
       - revenue_logs.type            ("sale"  | "refund" | "discount")

  2. Adds CHECK constraints on ALL enum-bearing columns (both native ENUM
     and VARCHAR) to give a hard DB-level guarantee that no out-of-contract
     value can ever be written. For native ENUM columns the constraint is
     technically redundant but serves as explicit documentation and guards
     against future ALTER TYPE accidents.

Why no UPDATE on native ENUM columns
--------------------------------------
PostgreSQL ENUM columns cannot be the target of:
    UPDATE t SET col = LOWER(TRIM(col::text))::text
because the right-hand side is type TEXT and the column type is the ENUM.
The correct cast would be ::enum_type_name, which is data-dependent.
Since 018–020 already lowercased every value via USING LOWER(col::text),
there is nothing to normalise — skipping is correct.

CHECK constraint casting strategy
----------------------------------
For native ENUM columns, the IN-list literals must match ENUM values exactly,
so plain CHECK (col IN ('a','b')) works. We cast col::text as a belt-and-
braces measure so the expression compiles identically on both ENUM and
VARCHAR columns.

Revision ID: 021_enum_string_constraints
Revises:     020_enum_lowercase
"""

from alembic import op

revision = "021_enum_string_constraints"
down_revision = "020_enum_lowercase"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_varchar(table: str, column: str) -> None:
    """
    Lowercase-trim a plain VARCHAR column.
    Only safe to call on VARCHAR columns — NOT on native PG ENUM columns.
    Migrations 018-020 already handled all native ENUM columns.
    """
    op.execute(
        f"UPDATE {table} "
        f"SET {column} = LOWER(TRIM({column})) "
        f"WHERE {column} IS NOT NULL "
        f"AND {column} != LOWER(TRIM({column}))"
    )


def _add_check(constraint_name: str, table: str, column: str, values: list[str]) -> None:
    """
    Add a CHECK constraint for allowed enum values.
    Casts column to ::text so the expression works uniformly on both
    native ENUM columns and VARCHAR columns.
    Nullable-safe: NULL values pass through (IS NULL OR ...).
    """
    values_sql = ", ".join(f"'{v}'" for v in values)
    op.execute(
        f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} "
        f"CHECK ({column} IS NULL OR {column}::text IN ({values_sql}))"
    )


def _drop_check(constraint_name: str, table: str) -> None:
    op.execute(
        f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint_name}"
    )


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:

    # ── Step 1: Normalise the three VARCHAR-only columns (018-020 skipped) ─

    _normalise_varchar("users",          "auth_provider")
    _normalise_varchar("ticket_replies", "author_type")
    _normalise_varchar("revenue_logs",   "type")

    # ── Step 2: CHECK constraints on all enum columns ──────────────────────
    # Native ENUM columns (already lowercase from 018-020) — belt-and-braces:

    _add_check(
        "ck_orders_status", "orders", "status",
        ["pending", "paid", "processing", "shipped", "out_for_delivery",
         "delivered", "cancelled", "returned", "refunded"],
    )

    _add_check(
        "ck_users_role", "users", "role",
        ["customer", "staff", "admin", "super_admin"],
    )

    _add_check(
        "ck_payments_method", "payments", "method",
        ["razorpay", "cod"],
    )

    _add_check(
        "ck_payments_status", "payments", "status",
        ["pending", "success", "failed", "refunded", "partially_refunded"],
    )

    _add_check(
        "ck_shipments_status", "shipments", "status",
        ["pending", "picked_up", "in_transit", "out_for_delivery",
         "delivered", "failed_delivery", "returned"],
    )

    _add_check(
        "ck_return_requests_status", "return_requests", "status",
        ["requested", "approved", "rejected", "picked_up",
         "refund_initiated", "completed"],
    )

    _add_check(
        "ck_support_tickets_status", "support_tickets", "status",
        ["open", "in_progress", "waiting_for_customer", "resolved", "closed"],
    )

    _add_check(
        "ck_support_tickets_priority", "support_tickets", "priority",
        ["low", "medium", "high"],
    )

    _add_check(
        "ck_products_status", "products", "status",
        ["active", "inactive", "out_of_stock", "draft"],
    )

    _add_check(
        "ck_products_difficulty_level", "products", "difficulty_level",
        ["beginner", "intermediate", "advanced"],
    )

    _add_check(
        "ck_products_gender", "products", "gender",
        ["male", "female", "unisex", "boys", "girls"],
    )

    _add_check(
        "ck_coupons_discount_type", "coupons", "discount_type",
        ["percentage", "fixed"],
    )

    _add_check(
        "ck_inventory_reservations_status", "inventory_reservations", "status",
        ["active", "confirmed", "released"],
    )

    # VARCHAR-only columns (normalised in Step 1 above):

    _add_check(
        "ck_users_auth_provider", "users", "auth_provider",
        ["local", "google"],
    )

    _add_check(
        "ck_ticket_replies_author_type", "ticket_replies", "author_type",
        ["user", "admin"],
    )

    _add_check(
        "ck_revenue_logs_type", "revenue_logs", "type",
        ["sale", "refund", "discount"],
    )


# ---------------------------------------------------------------------------
# Downgrade — removes CHECK constraints only (data is not reverted)
# ---------------------------------------------------------------------------

def downgrade() -> None:
    _drop_check("ck_revenue_logs_type",              "revenue_logs")
    _drop_check("ck_ticket_replies_author_type",     "ticket_replies")
    _drop_check("ck_users_auth_provider",            "users")
    _drop_check("ck_inventory_reservations_status",  "inventory_reservations")
    _drop_check("ck_coupons_discount_type",          "coupons")
    _drop_check("ck_products_gender",                "products")
    _drop_check("ck_products_difficulty_level",      "products")
    _drop_check("ck_products_status",                "products")
    _drop_check("ck_support_tickets_priority",       "support_tickets")
    _drop_check("ck_support_tickets_status",         "support_tickets")
    _drop_check("ck_return_requests_status",         "return_requests")
    _drop_check("ck_shipments_status",               "shipments")
    _drop_check("ck_payments_status",                "payments")
    _drop_check("ck_payments_method",                "payments")
    _drop_check("ck_users_role",                     "users")
    _drop_check("ck_orders_status",                  "orders")
