"""product search indexes for admin autocomplete

Revision ID: 009
Revises: 008
Create Date: 2026-03-04

What this migration does
------------------------
Adds explicit DB-level indexes to speed up the admin product search endpoint
(GET /admin/products/search?q=) which filters by:

  1. products.name   — ILIKE match on product title
  2. products.sku    — ILIKE match on SKU code
  3. products.category_id — JOIN to categories; FK column benefits from index

products.name already carries a SQLAlchemy `index=True`, so its index may
already exist.  All creates use `if_not_exists=True` / `checkfirst=True` so
this migration is idempotent.

Backward compatibility
----------------------
* No columns are altered or dropped.
* Downgrade simply removes the three indexes.
"""
from alembic import op


revision      = '009'
down_revision = '008'
branch_labels = None
depends_on    = None


def upgrade():
    # ── 1. products.name ──────────────────────────────────────────────────
    # SQLAlchemy model has index=True; this is a belt-and-suspenders addition.
    op.create_index(
        'ix_products_name',
        'products', ['name'],
        unique=False,
        if_not_exists=True,
    )

    # ── 2. products.sku ───────────────────────────────────────────────────
    # Already has unique=True which creates a unique index, but we add an
    # explicit non-unique index for ILIKE scans on non-PG databases.
    op.create_index(
        'ix_products_sku',
        'products', ['sku'],
        unique=False,
        if_not_exists=True,
    )

    # ── 3. products.category_id ───────────────────────────────────────────
    # ForeignKey creates a constraint but not always an index (SQLite).
    op.create_index(
        'ix_products_category_id',
        'products', ['category_id'],
        unique=False,
        if_not_exists=True,
    )


def downgrade():
    op.drop_index('ix_products_category_id', table_name='products', if_exists=True)
    op.drop_index('ix_products_sku',         table_name='products', if_exists=True)
    op.drop_index('ix_products_name',        table_name='products', if_exists=True)
