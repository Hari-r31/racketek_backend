"""Add bundle_discount_per_item and bundle_discount_max_cap to bundle_builder section

Revision ID: 010_bundle_discount_settings
Revises: 009_product_search_indexes
Create Date: 2026-03-04
"""
import json
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

revision      = "010_bundle_discount_settings"
down_revision = "009"
branch_labels = None
depends_on    = None

SECTION_KEY     = "bundle_builder"
NEW_FIELDS      = {
    "bundle_discount_per_item": 5,
    "bundle_discount_max_cap":  50,
}


def upgrade() -> None:
    """
    If a bundle_builder row already exists in homepage_content, merge the two
    new discount settings into its content JSON (only if keys are absent).
    New installs will pick up the values from DEFAULT_CONTENT automatically.
    """
    conn = op.get_bind()

    row = conn.execute(
        text("SELECT id, content FROM homepage_content WHERE section_key = :key"),
        {"key": SECTION_KEY},
    ).fetchone()

    if row is None:
        # Table is empty / section not seeded yet — nothing to do.
        # DEFAULT_CONTENT already carries the new keys for fresh seeds.
        return

    row_id  = row[0]
    content = row[1]

    # content may be stored as a dict (JSONB) or a str (JSON text on SQLite)
    if isinstance(content, str):
        content = json.loads(content)

    changed = False
    for field, default_value in NEW_FIELDS.items():
        if field not in content:
            content[field] = default_value
            changed = True

    if changed:
        conn.execute(
            text(
                "UPDATE homepage_content SET content = :content WHERE id = :id"
            ),
            {"content": json.dumps(content), "id": row_id},
        )


def downgrade() -> None:
    """Remove the new discount keys from the bundle_builder row."""
    conn = op.get_bind()

    row = conn.execute(
        text("SELECT id, content FROM homepage_content WHERE section_key = :key"),
        {"key": SECTION_KEY},
    ).fetchone()

    if row is None:
        return

    row_id  = row[0]
    content = row[1]

    if isinstance(content, str):
        content = json.loads(content)

    for field in NEW_FIELDS:
        content.pop(field, None)

    conn.execute(
        text("UPDATE homepage_content SET content = :content WHERE id = :id"),
        {"content": json.dumps(content), "id": row_id},
    )
