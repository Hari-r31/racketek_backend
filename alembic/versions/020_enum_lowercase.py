"""
Migration 020 — Normalise all enum values: UPPERCASE → lowercase

Enums converted:
  - userrole          (users.role):              CUSTOMER/STAFF/ADMIN/SUPER_ADMIN
  - shipmentstatus    (shipments.status):         PENDING/PICKED_UP/IN_TRANSIT/…
  - paymentmethod     (payments.method):          RAZORPAY/COD
  - paymentstatus     (payments.status):          PENDING/SUCCESS/FAILED/REFUNDED/…
  - returnstatus      (return_requests.status):   REQUESTED/APPROVED/REJECTED/…
  - ticketstatus      (support_tickets.status):   OPEN/IN_PROGRESS/…
  - ticketpriority    (support_tickets.priority): LOW/MEDIUM/HIGH
  - discounttype      (coupons.discount_type):    PERCENTAGE/FIXED
  - productstatus     (products.status):          ACTIVE/INACTIVE/OUT_OF_STOCK/DRAFT
  - difficultylevel   (products.difficulty_level): BEGINNER/INTERMEDIATE/ADVANCED
  - gendercategory    (products.gender):          MALE/FEMALE/UNISEX/BOYS/GIRLS

Strategy (same as migration 018/019):
  For each enum:
    1. Drop column default
    2. Create <name>_new enum with lowercase values
    3. ALTER COLUMN … USING LOWER(col::text)::<name>_new
    4. DROP old type, RENAME new type

Revision ID: 020_enum_lowercase
Revises:     019_orders_status_enum_lowercase
"""

from alembic import op
import sqlalchemy as sa

revision = "020_enum_lowercase"
down_revision = "019_orders_status_enum_lowercase"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Helper to convert a single enum column in-place
# ---------------------------------------------------------------------------
def _convert_enum(
    table: str,
    column: str,
    old_type_name: str,
    new_values: list,
    default: str | None = None,
):
    """
    Convert an existing PostgreSQL ENUM column to a new enum with `new_values`.
    Existing stored values are lower-cased during the conversion.
    """
    new_type_name = f"{old_type_name}_new"
    values_sql = ", ".join(f"'{v}'" for v in new_values)

    # 1. Drop default so we can change the column type
    op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT")

    # 2. New enum type
    op.execute(f"CREATE TYPE {new_type_name} AS ENUM ({values_sql})")

    # 3. Convert column (NULL-safe via CASE)
    op.execute(f"""
        ALTER TABLE {table}
        ALTER COLUMN {column} TYPE {new_type_name}
        USING LOWER({column}::text)::{new_type_name}
    """)

    # 4. Drop old, rename new
    op.execute(f"DROP TYPE IF EXISTS {old_type_name}")
    op.execute(f"ALTER TYPE {new_type_name} RENAME TO {old_type_name}")

    # 5. Restore default (if any)
    if default:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT '{default}'"
        )


def upgrade() -> None:
    # ── users.role ────────────────────────────────────────────────────────
    _convert_enum(
        "users", "role", "userrole",
        ["customer", "staff", "admin", "super_admin"],
        default="customer",
    )

    # ── shipments.status ──────────────────────────────────────────────────
    _convert_enum(
        "shipments", "status", "shipmentstatus",
        ["pending", "picked_up", "in_transit", "out_for_delivery",
         "delivered", "failed_delivery", "returned"],
        default="pending",
    )

    # ── payments.method ───────────────────────────────────────────────────
    _convert_enum(
        "payments", "method", "paymentmethod",
        ["razorpay", "cod"],
    )

    # ── payments.status ───────────────────────────────────────────────────
    _convert_enum(
        "payments", "status", "paymentstatus",
        ["pending", "success", "failed", "refunded", "partially_refunded"],
        default="pending",
    )

    # ── return_requests.status ────────────────────────────────────────────
    _convert_enum(
        "return_requests", "status", "returnstatus",
        ["requested", "approved", "rejected", "picked_up",
         "refund_initiated", "completed"],
        default="requested",
    )

    # ── support_tickets.status ────────────────────────────────────────────
    _convert_enum(
        "support_tickets", "status", "ticketstatus",
        ["open", "in_progress", "waiting_for_customer", "resolved", "closed"],
        default="open",
    )

    # ── support_tickets.priority ──────────────────────────────────────────
    _convert_enum(
        "support_tickets", "priority", "ticketpriority",
        ["low", "medium", "high"],
        default="medium",
    )

    # ── coupons.discount_type ─────────────────────────────────────────────
    _convert_enum(
        "coupons", "discount_type", "discounttype",
        ["percentage", "fixed"],
    )

    # ── products.status ───────────────────────────────────────────────────
    _convert_enum(
        "products", "status", "productstatus",
        ["active", "inactive", "out_of_stock", "draft"],
        default="active",
    )

    # ── products.difficulty_level ─────────────────────────────────────────
    # This column is nullable — no default needed
    _convert_enum(
        "products", "difficulty_level", "difficultylevel",
        ["beginner", "intermediate", "advanced"],
    )

    # ── products.gender ───────────────────────────────────────────────────
    # This column is nullable — no default needed
    _convert_enum(
        "products", "gender", "gendercategory",
        ["male", "female", "unisex", "boys", "girls"],
    )


def downgrade() -> None:
    """Reverse all conversions: lowercase → UPPERCASE."""

    def _revert(table, column, type_name, upper_values, default=None):
        new_type_name = f"{type_name}_old"
        values_sql = ", ".join(f"'{v}'" for v in upper_values)
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT")
        op.execute(f"CREATE TYPE {new_type_name} AS ENUM ({values_sql})")
        op.execute(f"""
            ALTER TABLE {table}
            ALTER COLUMN {column} TYPE {new_type_name}
            USING UPPER({column}::text)::{new_type_name}
        """)
        op.execute(f"DROP TYPE {type_name}")
        op.execute(f"ALTER TYPE {new_type_name} RENAME TO {type_name}")
        if default:
            op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT '{default}'")

    _revert("products",       "gender",          "gendercategory",  ["MALE","FEMALE","UNISEX","BOYS","GIRLS"])
    _revert("products",       "difficulty_level","difficultylevel", ["BEGINNER","INTERMEDIATE","ADVANCED"])
    _revert("products",       "status",          "productstatus",   ["ACTIVE","INACTIVE","OUT_OF_STOCK","DRAFT"], "ACTIVE")
    _revert("coupons",        "discount_type",   "discounttype",    ["PERCENTAGE","FIXED"])
    _revert("support_tickets","priority",        "ticketpriority",  ["LOW","MEDIUM","HIGH"], "MEDIUM")
    _revert("support_tickets","status",          "ticketstatus",    ["OPEN","IN_PROGRESS","WAITING_FOR_CUSTOMER","RESOLVED","CLOSED"], "OPEN")
    _revert("return_requests","status",          "returnstatus",    ["REQUESTED","APPROVED","REJECTED","PICKED_UP","REFUND_INITIATED","COMPLETED"], "REQUESTED")
    _revert("payments",       "status",          "paymentstatus",   ["PENDING","SUCCESS","FAILED","REFUNDED","PARTIALLY_REFUNDED"], "PENDING")
    _revert("payments",       "method",          "paymentmethod",   ["RAZORPAY","COD"])
    _revert("shipments",      "status",          "shipmentstatus",  ["PENDING","PICKED_UP","IN_TRANSIT","OUT_FOR_DELIVERY","DELIVERED","FAILED_DELIVERY","RETURNED"], "PENDING")
    _revert("users",          "role",            "userrole",        ["CUSTOMER","STAFF","ADMIN","SUPER_ADMIN"], "CUSTOMER")
