"""change products.meta_description from VARCHAR(500) to TEXT

Revision ID: 013_product_meta_description_text
Revises: 012_users_otp_columns
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision      = "013_meta_desc_text"
down_revision = "012_users_otp_columns"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    bind      = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns   = {c["name"]: c for c in inspector.get_columns("products")}

    col = columns.get("meta_description")
    if col is not None:
        # Cast VARCHAR(500) → TEXT so long SEO descriptions are never truncated
        op.alter_column(
            "products",
            "meta_description",
            existing_type=sa.String(500),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    # Revert TEXT → VARCHAR(500).  Any values longer than 500 chars will be
    # truncated by Postgres during the cast — intentional for a downgrade.
    op.alter_column(
        "products",
        "meta_description",
        existing_type=sa.Text(),
        type_=sa.String(500),
        existing_nullable=True,
        postgresql_using="meta_description::character varying(500)",
    )
