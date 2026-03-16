"""
Alembic migration 014 — Add difficulty_level, gender to products;
add awb_number, tracking_url to orders.

Revision ID: 014_product_difficulty_gender_awb
Revises: 013_meta_desc_text
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision      = "014_product_difficulty_gender_awb"
down_revision = "013_meta_desc_text"
branch_labels = None
depends_on    = None


def _column_exists(inspector: Inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind      = op.get_bind()
    inspector = Inspector.from_engine(bind)

    # ── products table ────────────────────────────────────────────────────────

    # difficulty_level  — BUG 1 fix
    if not _column_exists(inspector, "products", "difficulty_level"):
        op.add_column(
            "products",
            sa.Column(
                "difficulty_level",
                sa.String(50),
                nullable=True,
                comment="Skill level: beginner, intermediate, advanced",
            ),
        )

    # gender  — FEATURE 2 fix
    if not _column_exists(inspector, "products", "gender"):
        op.add_column(
            "products",
            sa.Column(
                "gender",
                sa.String(20),
                nullable=True,
                comment="Gender classification: male, female, unisex, boys, girls",
            ),
        )

    # ── orders table ──────────────────────────────────────────────────────────

    # awb_number  — BUG 4 fix
    if not _column_exists(inspector, "orders", "awb_number"):
        op.add_column(
            "orders",
            sa.Column(
                "awb_number",
                sa.String(200),
                nullable=True,
                comment="Air Waybill / courier tracking number",
            ),
        )

    # tracking_url  — BUG 4 fix
    if not _column_exists(inspector, "orders", "tracking_url"):
        op.add_column(
            "orders",
            sa.Column(
                "tracking_url",
                sa.String(500),
                nullable=True,
                comment="Direct link to courier tracking page",
            ),
        )


def downgrade() -> None:
    bind      = op.get_bind()
    inspector = Inspector.from_engine(bind)

    for col in ("awb_number", "tracking_url"):
        if _column_exists(inspector, "orders", col):
            op.drop_column("orders", col)

    for col in ("gender", "difficulty_level"):
        if _column_exists(inspector, "products", col):
            op.drop_column("products", col)
