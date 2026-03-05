"""add OTP columns and is_phone_verified to users

Revision ID: 012_users_otp_columns
Revises: 011_support_tickets_upgrade
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision      = "012_users_otp_columns"
down_revision = "011_support_tickets_upgrade"
branch_labels = None
depends_on    = None

NEW_COLUMNS = [
    ("is_phone_verified",  sa.Boolean(),     {"nullable": True,  "server_default": "false"}),
    ("email_otp",          sa.String(64),    {"nullable": True}),
    ("email_otp_expiry",   sa.DateTime(),    {"nullable": True}),
    ("phone_otp",          sa.String(64),    {"nullable": True}),
    ("phone_otp_expiry",   sa.DateTime(),    {"nullable": True}),
    ("reset_otp",          sa.String(64),    {"nullable": True}),
    ("reset_otp_expiry",   sa.DateTime(),    {"nullable": True}),
    ("reset_otp_contact",  sa.String(255),   {"nullable": True}),
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
