"""
Migration 018 — Fix reservationstatus enum (UPPERCASE → lowercase)

- Converts existing ENUM values to lowercase
- Uses safe enum replacement strategy
"""

from alembic import op
import sqlalchemy as sa

revision = "018_inventory_reservation_enum"
down_revision = "017_product_catalog_upgrade"
branch_labels = None
depends_on = None

_TABLE = "inventory_reservations"


def upgrade() -> None:
    # 1. Create new enum (lowercase)
    op.execute(
        sa.text(
            "CREATE TYPE reservationstatus_new AS ENUM ('active', 'confirmed', 'released')"
        )
    )

    # 2. Convert column using cast
    op.execute(
        sa.text(
            """
            ALTER TABLE inventory_reservations
            ALTER COLUMN status TYPE reservationstatus_new
            USING LOWER(status::text)::reservationstatus_new
            """
        )
    )

    # 3. Drop old enum
    op.execute(sa.text("DROP TYPE reservationstatus"))

    # 4. Rename new enum
    op.execute(
        sa.text(
            "ALTER TYPE reservationstatus_new RENAME TO reservationstatus"
        )
    )


def downgrade() -> None:
    # Reverse (lowercase → uppercase)

    op.execute(
        sa.text(
            "CREATE TYPE reservationstatus_old AS ENUM ('ACTIVE', 'CONFIRMED', 'RELEASED')"
        )
    )

    op.execute(
        sa.text(
            """
            ALTER TABLE inventory_reservations
            ALTER COLUMN status TYPE reservationstatus_old
            USING UPPER(status::text)::reservationstatus_old
            """
        )
    )

    op.execute(sa.text("DROP TYPE reservationstatus"))

    op.execute(
        sa.text(
            "ALTER TYPE reservationstatus_old RENAME TO reservationstatus"
        )
    )