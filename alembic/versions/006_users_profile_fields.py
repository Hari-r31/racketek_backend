"""Add extended profile fields to users table

Revision ID: 006_users_profile_fields
Revises: 005_homepage_content_seed
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision      = "006_users_profile_fields"
down_revision = "005_homepage_content_seed"
branch_labels = None
depends_on    = None

NEW_COLUMNS = [
    ("date_of_birth", sa.String(20),  {"nullable": True}),
    ("address_line1", sa.String(300), {"nullable": True}),
    ("city",          sa.String(100), {"nullable": True}),
    ("state",         sa.String(100), {"nullable": True}),
    ("pincode",       sa.String(10),  {"nullable": True}),
]


def upgrade() -> None:
    conn      = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing  = {c["name"] for c in inspector.get_columns("users")}

    for col_name, col_type, col_kwargs in NEW_COLUMNS:
        if col_name not in existing:
            op.add_column("users", sa.Column(col_name, col_type, **col_kwargs))


def downgrade() -> None:
    conn      = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing  = {c["name"] for c in inspector.get_columns("users")}

    for col_name, _, _ in reversed(NEW_COLUMNS):
        if col_name in existing:
            op.drop_column("users", col_name)
