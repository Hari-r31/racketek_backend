"""create homepage_content table

Revision ID: 001_homepage_content
Revises:
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = "001_homepage_content"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if the table already exists before trying to create it.
    # (Handles the case where the table was created by create_all() directly.)
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing_tables = inspector.get_table_names()

    if "homepage_content" not in existing_tables:
        op.create_table(
            "homepage_content",
            sa.Column("id",          sa.Integer(),   nullable=False, autoincrement=True),
            sa.Column("section_key", sa.String(100), nullable=False),
            sa.Column("content",     sa.JSON(),       nullable=False, server_default="{}"),
            sa.Column("is_active",   sa.Boolean(),    nullable=False, server_default="true"),
            sa.Column("updated_by",  sa.Integer(),    nullable=True),
            sa.Column("updated_at",  sa.DateTime(),   nullable=True),
            sa.Column("created_at",  sa.DateTime(),   nullable=True, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("section_key"),
        )
        op.create_index("ix_homepage_content_id",          "homepage_content", ["id"],          unique=False)
        op.create_index("ix_homepage_content_section_key", "homepage_content", ["section_key"], unique=True)
    else:
        # Table already exists — ensure indexes exist (idempotent)
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("homepage_content")}
        if "ix_homepage_content_id" not in existing_indexes:
            op.create_index("ix_homepage_content_id", "homepage_content", ["id"], unique=False)
        if "ix_homepage_content_section_key" not in existing_indexes:
            op.create_index("ix_homepage_content_section_key", "homepage_content", ["section_key"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    if "homepage_content" in inspector.get_table_names():
        op.drop_index("ix_homepage_content_section_key", table_name="homepage_content")
        op.drop_index("ix_homepage_content_id",          table_name="homepage_content")
        op.drop_table("homepage_content")
