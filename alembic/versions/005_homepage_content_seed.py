"""create homepage_content table if not exists + seed all 14 section keys

Revision ID: 005_homepage_content_seed
Revises: 004_users_token_columns
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision      = "005_homepage_content_seed"
down_revision = "004_users_token_columns"
branch_labels = None
depends_on    = None

TABLE = "homepage_content"

ALL_SECTIONS = [
    "announcement_bar",
    "hero_banners",
    "quick_categories",
    "movement_section",
    "homepage_videos",
    "featured_product",
    "crafted_section",
    "bundle_builder",
    "deal_of_day",
    "shop_the_look",
    "testimonials",
    "featured_collections",
    "brand_spotlight",
    "about_section",
]


def upgrade() -> None:
    conn      = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    # 1. Create table if missing
    if TABLE not in existing_tables:
        op.create_table(
            TABLE,
            sa.Column("id",          sa.Integer,     primary_key=True, autoincrement=True),
            sa.Column("section_key", sa.String(100), unique=True, nullable=False),
            sa.Column("content",     sa.JSON,        nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("is_active",   sa.Boolean,     nullable=False, server_default=sa.text("true")),
            sa.Column("updated_by",  sa.Integer,     nullable=True),
            sa.Column("updated_at",  sa.DateTime,    nullable=True,  server_default=sa.text("NOW()")),
            sa.Column("created_at",  sa.DateTime,    nullable=False, server_default=sa.text("NOW()")),
        )
        # Refresh inspector after table creation
        inspector = Inspector.from_engine(conn)

    # 2. Create index on section_key only if it doesn't already exist
    #    (Using Inspector avoids the try/except DDL-aborts-transaction problem in PostgreSQL)
    existing_indexes = {idx["name"] for idx in inspector.get_indexes(TABLE)}
    if f"ix_{TABLE}_section_key" not in existing_indexes:
        op.create_index(f"ix_{TABLE}_section_key", TABLE, ["section_key"], unique=True)

    # 3. Seed any missing section keys with empty content {}
    existing_keys = {
        row[0]
        for row in conn.execute(sa.text(f"SELECT section_key FROM {TABLE}"))
    }

    to_insert = [k for k in ALL_SECTIONS if k not in existing_keys]

    if to_insert:
        for k in to_insert:
            conn.execute(
                sa.text(
                    f"INSERT INTO {TABLE} (section_key, content, is_active, created_at, updated_at) "
                    f"VALUES (:section_key, CAST(:content AS json), :is_active, NOW(), NOW())"
                ),
                {"section_key": k, "content": "{}", "is_active": True},
            )


def downgrade() -> None:
    conn      = op.get_bind()
    inspector = Inspector.from_engine(conn)
    if TABLE in inspector.get_table_names():
        op.drop_table(TABLE)
