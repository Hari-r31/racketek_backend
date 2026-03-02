"""add sort_order to categories table

Revision ID: 002_categories_sort_order
Revises: 001_homepage_content
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = "002_categories_sort_order"
down_revision = "001_homepage_content"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)

    existing_columns = [col["name"] for col in inspector.get_columns("categories")]

    if "sort_order" not in existing_columns:
        op.add_column(
            "categories",
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing_columns = [col["name"] for col in inspector.get_columns("categories")]
    if "sort_order" in existing_columns:
        op.drop_column("categories", "sort_order")
