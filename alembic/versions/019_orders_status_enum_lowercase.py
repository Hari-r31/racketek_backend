"""
Migration 019 — Fix orderstatus enum: UPPERCASE → lowercase

The OrderStatus Python enum previously used UPPERCASE values ("PENDING", "PAID", …).
The frontend always sends lowercase ("pending", "paid", …) which caused
422 Unprocessable Entity on every status filter and status-update call.

This migration renames the existing orderstatus enum type and converts all
stored values to lowercase, matching the updated Python enum.

Revision ID: 019_orders_status_enum_lowercase
Revises:     018_inventory_reservation_enum
"""

from alembic import op
import sqlalchemy as sa

revision = "019_orders_status_enum_lowercase"
down_revision = "018_inventory_reservation_enum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop the column default (if any)
    op.execute("ALTER TABLE orders ALTER COLUMN status DROP DEFAULT")

    # 2. Create the new lowercase enum
    op.execute("""
        CREATE TYPE orderstatus_new AS ENUM (
            'pending', 'paid', 'processing', 'shipped',
            'out_for_delivery', 'delivered',
            'cancelled', 'returned', 'refunded'
        )
    """)

    # 3. Convert the column: cast current value to text, lower-case it,
    #    then cast to the new enum type.
    op.execute("""
        ALTER TABLE orders
        ALTER COLUMN status TYPE orderstatus_new
        USING LOWER(status::text)::orderstatus_new
    """)

    # 4. Drop the old enum type
    op.execute("DROP TYPE IF EXISTS orderstatus")

    # 5. Rename new type to the canonical name
    op.execute("ALTER TYPE orderstatus_new RENAME TO orderstatus")

    # 6. Restore the default
    op.execute("ALTER TABLE orders ALTER COLUMN status SET DEFAULT 'pending'")


def downgrade() -> None:
    # Reverse: lowercase → UPPERCASE

    op.execute("ALTER TABLE orders ALTER COLUMN status DROP DEFAULT")

    op.execute("""
        CREATE TYPE orderstatus_old AS ENUM (
            'PENDING', 'PAID', 'PROCESSING', 'SHIPPED',
            'OUT_FOR_DELIVERY', 'DELIVERED',
            'CANCELLED', 'RETURNED', 'REFUNDED'
        )
    """)

    op.execute("""
        ALTER TABLE orders
        ALTER COLUMN status TYPE orderstatus_old
        USING UPPER(status::text)::orderstatus_old
    """)

    op.execute("DROP TYPE orderstatus")
    op.execute("ALTER TYPE orderstatus_old RENAME TO orderstatus")
    op.execute("ALTER TABLE orders ALTER COLUMN status SET DEFAULT 'PENDING'")
