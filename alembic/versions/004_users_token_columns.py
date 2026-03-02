"""add email_verify_token and password_reset_token columns to users

Revision ID: 004_users_token_columns
Revises: 003_users_updated_at
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision      = "004_users_token_columns"
down_revision = "003_users_updated_at"
branch_labels = None
depends_on    = None

# Columns to add: (name, type, kwargs)
NEW_COLUMNS = [
    ("email_verify_token",        sa.String(256), {"nullable": True}),
    ("email_verify_token_expiry", sa.DateTime(),  {"nullable": True}),
    ("password_reset_token",      sa.String(256), {"nullable": True}),
    ("password_reset_token_expiry", sa.DateTime(), {"nullable": True}),
]


def upgrade() -> None:
    bind      = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing  = {c["name"] for c in inspector.get_columns("users")}

    for col_name, col_type, col_kwargs in NEW_COLUMNS:
        if col_name not in existing:
            op.add_column("users", sa.Column(col_name, col_type, **col_kwargs))


def downgrade() -> None:
    bind      = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing  = {c["name"] for c in inspector.get_columns("users")}

    for col_name, _, _ in reversed(NEW_COLUMNS):
        if col_name in existing:
            op.drop_column("users", col_name)
