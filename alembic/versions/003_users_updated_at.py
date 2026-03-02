"""add updated_at to users table if missing

Revision ID: 003_users_updated_at
Revises: 002_categories_sort_order
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision      = "003_users_updated_at"
down_revision = "002_categories_sort_order"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    bind      = op.get_bind()
    inspector = Inspector.from_engine(bind)
    cols      = [c["name"] for c in inspector.get_columns("users")]

    if "updated_at" not in cols:
        op.add_column(
            "users",
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=True,
                server_default=sa.func.now(),
            ),
        )


def downgrade() -> None:
    bind      = op.get_bind()
    inspector = Inspector.from_engine(bind)
    cols      = [c["name"] for c in inspector.get_columns("users")]
    if "updated_at" in cols:
        op.drop_column("users", "updated_at")
