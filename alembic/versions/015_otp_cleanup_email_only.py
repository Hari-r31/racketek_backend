"""
Migration 015 — Remove phone OTP & legacy token columns from users;
                add OTP attempt tracking and purpose columns.

Changes:
  DROP   phone_otp
  DROP   phone_otp_expiry
  DROP   is_phone_verified
  DROP   reset_otp_contact          (was "email or phone")
  DROP   email_verify_token         (legacy link-based flow)
  DROP   email_verify_token_expiry
  DROP   password_reset_token       (legacy token flow)
  DROP   password_reset_token_expiry

  ADD    email_otp_attempts   INTEGER  nullable default 0
  ADD    email_otp_purpose    VARCHAR(30) nullable
  ADD    reset_otp_attempts   INTEGER  nullable default 0

Revision ID: 015_otp_cleanup_email_only
Revises: 014_product_diff_gender_awb
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision      = "015_otp_cleanup_email_only"
down_revision = "014_product_diff_gender_awb"
branch_labels = None
depends_on    = None

# Columns to DROP (phone OTP + legacy tokens)
COLS_TO_DROP = [
    "phone_otp",
    "phone_otp_expiry",
    "is_phone_verified",
    "reset_otp_contact",
    "email_verify_token",
    "email_verify_token_expiry",
    "password_reset_token",
    "password_reset_token_expiry",
]

# Columns to ADD (attempt tracking + purpose)
COLS_TO_ADD = [
    ("email_otp_attempts", sa.Integer(),    {"nullable": True, "server_default": "0"}),
    ("email_otp_purpose",  sa.String(30),   {"nullable": True}),
    ("reset_otp_attempts", sa.Integer(),    {"nullable": True, "server_default": "0"}),
]


def _has_column(inspector: Inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind      = op.get_bind()
    inspector = Inspector.from_engine(bind)

    # 1. Drop obsolete columns (idempotent — skips if already gone)
    for col_name in COLS_TO_DROP:
        if _has_column(inspector, "users", col_name):
            op.drop_column("users", col_name)

    # 2. Add new columns (idempotent — skips if already present)
    for col_name, col_type, col_kwargs in COLS_TO_ADD:
        if not _has_column(inspector, "users", col_name):
            op.add_column("users", sa.Column(col_name, col_type, **col_kwargs))


def downgrade() -> None:
    bind      = op.get_bind()
    inspector = Inspector.from_engine(bind)

    # Remove added columns
    for col_name, _, _ in reversed(COLS_TO_ADD):
        if _has_column(inspector, "users", col_name):
            op.drop_column("users", col_name)

    # Re-add dropped columns (nullable, no data restored)
    legacy_cols = [
        ("phone_otp",                   sa.String(64),  {"nullable": True}),
        ("phone_otp_expiry",            sa.DateTime(),  {"nullable": True}),
        ("is_phone_verified",           sa.Boolean(),   {"nullable": True, "server_default": "false"}),
        ("reset_otp_contact",           sa.String(255), {"nullable": True}),
        ("email_verify_token",          sa.String(256), {"nullable": True}),
        ("email_verify_token_expiry",   sa.DateTime(),  {"nullable": True}),
        ("password_reset_token",        sa.String(256), {"nullable": True}),
        ("password_reset_token_expiry", sa.DateTime(),  {"nullable": True}),
    ]
    for col_name, col_type, col_kwargs in legacy_cols:
        if not _has_column(inspector, "users", col_name):
            op.add_column("users", sa.Column(col_name, col_type, **col_kwargs))
