"""
Migration 018 — InventoryReservation enum introduction

- Creates PostgreSQL enum `reservationstatus`
- Converts existing `status` column from TEXT → ENUM
- Ensures safe casting using LOWER()
- Idempotent and production-safe
"""

from alembic import op
import sqlalchemy as sa

# ── Revision identifiers ───────────────────────────────────────────────────
revision = "018_inventory_reservation_enum"
down_revision = "017_product_catalog_upgrade"
branch_labels = None
depends_on = None

_TABLE = "inventory_reservations"
_ENUM_NAME = "reservationstatus"
_ENUM_VALUES = ("active", "confirmed", "released")


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. Create enum if not exists ───────────────────────────────────────
    enum_exists = bind.execute(
        sa.text(
            f"""
            SELECT 1 FROM pg_type WHERE typname = '{_ENUM_NAME}'
            """
        )
    ).fetchone()

    if not enum_exists:
        op.execute(
            sa.text(
                f"CREATE TYPE {_ENUM_NAME} AS ENUM {str(_ENUM_VALUES)}"
            )
        )

    # ── 2. Normalize existing data (VERY IMPORTANT) ────────────────────────
    # Handles cases like 'ACTIVE' → 'active'
    op.execute(
        sa.text(
            f"""
            UPDATE {_TABLE}
            SET status = LOWER(status)
            WHERE status IS NOT NULL
            """
        )
    )

    # ── 3. Alter column to ENUM ────────────────────────────────────────────
    op.execute(
        sa.text(
            f"""
            ALTER TABLE {_TABLE}
            ALTER COLUMN status TYPE {_ENUM_NAME}
            USING status::{_ENUM_NAME}
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()

    # ── 1. Convert ENUM → TEXT ─────────────────────────────────────────────
    op.execute(
        sa.text(
            f"""
            ALTER TABLE {_TABLE}
            ALTER COLUMN status TYPE TEXT
            USING status::text
            """
        )
    )

    # ── 2. Drop enum safely ────────────────────────────────────────────────
    enum_in_use = bind.execute(
        sa.text(
            f"""
            SELECT 1
            FROM pg_type t
            JOIN pg_depend d ON d.refobjid = t.oid
            WHERE t.typname = '{_ENUM_NAME}'
            LIMIT 1
            """
        )
    ).fetchone()

    if not enum_in_use:
        op.execute(sa.text(f"DROP TYPE IF EXISTS {_ENUM_NAME}"))