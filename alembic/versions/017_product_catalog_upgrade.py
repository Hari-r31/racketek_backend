"""
Migration 017 — Catalog v2: highlights, specifications, manufacturer_info, extra_data

Adds structured product metadata fields for Amazon/Flipkart-style catalog.

Safe guarantees:
- No full table rewrite
- Backward compatible
- Idempotent (safe to rerun)
- GIN index created CONCURRENTLY (no table lock)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# ── Revision identifiers ───────────────────────────────────────────────────
revision = "017_product_catalog_upgrade"
down_revision = "016"
branch_labels = None
depends_on = None

_TABLE = "products"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_cols = {c["name"] for c in inspector.get_columns(_TABLE)}
    existing_indexes = {idx["name"] for idx in inspector.get_indexes(_TABLE)}

    # ── 1. highlights ──────────────────────────────────────────────────────
    if "highlights" not in existing_cols:
        op.add_column(
            _TABLE,
            sa.Column(
                "highlights",
                JSONB(),
                nullable=True,
                server_default=sa.text("'[]'::jsonb"),
                comment="Bullet-point product highlights",
            ),
        )

    # ── 2. specifications ──────────────────────────────────────────────────
    if "specifications" not in existing_cols:
        op.add_column(
            _TABLE,
            sa.Column(
                "specifications",
                JSONB(),
                nullable=True,
                server_default=sa.text("'{}'::jsonb"),
                comment="Grouped specs: {section: {key: value}}",
            ),
        )

    # ── 3. manufacturer_info ───────────────────────────────────────────────
    if "manufacturer_info" not in existing_cols:
        op.add_column(
            _TABLE,
            sa.Column(
                "manufacturer_info",
                JSONB(),
                nullable=True,
                server_default=sa.text("'{}'::jsonb"),
                comment="Manufacturer / compliance metadata",
            ),
        )

    # ── 4. extra_data ──────────────────────────────────────────────────────
    if "extra_data" not in existing_cols:
        op.add_column(
            _TABLE,
            sa.Column(
                "extra_data",
                JSONB(),
                nullable=True,
                server_default=sa.text("'{}'::jsonb"),
                comment="Extensible metadata bucket",
            ),
        )

    # ── 5. GIN index (CONCURRENTLY, non-transactional) ─────────────────────
    if "ix_products_specifications_gin" not in existing_indexes:
        # Required: break out of transaction
        bind.execute(sa.text("COMMIT"))
        bind.execute(
            sa.text(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                "ix_products_specifications_gin "
                "ON products USING gin (specifications)"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()

    # Drop index first (CONCURRENTLY)
    bind.execute(sa.text("COMMIT"))
    bind.execute(
        sa.text(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_products_specifications_gin"
        )
    )

    inspector = sa.inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns(_TABLE)}

    # Drop columns safely
    for col in ("extra_data", "manufacturer_info", "specifications", "highlights"):
        if col in existing_cols:
            op.drop_column(_TABLE, col)