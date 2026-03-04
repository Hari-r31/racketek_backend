"""
Support ticket Alembic migration — production upgrade (fixed).

Revision: 011_support_tickets_upgrade
Revises:  010_bundle_discount_settings
"""

from datetime import datetime
from collections import defaultdict

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
from sqlalchemy import inspect

revision = "011_support_tickets_upgrade"
down_revision = "010_bundle_discount_settings"
branch_labels = None
depends_on = None


# ──────────────────────────────────────────────────────────────────────────────
# Upgrade
# ──────────────────────────────────────────────────────────────────────────────

def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    dialect = conn.dialect.name

    # 1️⃣ Extend enum (Postgres only)
    if dialect == "postgresql":
        conn.execute(text(
            "ALTER TYPE ticketstatus ADD VALUE IF NOT EXISTS 'waiting_for_customer'"
        ))

    existing_cols = {c["name"] for c in inspector.get_columns("support_tickets")}

    # 2️⃣ Add ticket_number column (nullable first)
    if "ticket_number" not in existing_cols:
        op.add_column(
            "support_tickets",
            sa.Column("ticket_number", sa.String(30), nullable=True),
        )

    # 3️⃣ Add image_urls column
    if "image_urls" not in existing_cols:
        if dialect == "postgresql":
            op.add_column(
                "support_tickets",
                sa.Column(
                    "image_urls",
                    sa.dialects.postgresql.JSONB,
                    nullable=False,
                    server_default=sa.text("'[]'::jsonb"),
                ),
            )
        else:
            op.add_column(
                "support_tickets",
                sa.Column("image_urls", sa.JSON(), nullable=False, server_default="[]"),
            )

    # 4️⃣ Backfill ticket_number SAFELY
    rows = conn.execute(text("""
        SELECT id, created_at
        FROM support_tickets
        WHERE ticket_number IS NULL
        ORDER BY id
    """)).fetchall()

    # Get current max per year to avoid duplicates
    existing_numbers = conn.execute(text("""
        SELECT ticket_number FROM support_tickets
        WHERE ticket_number IS NOT NULL
    """)).fetchall()

    counters = defaultdict(int)

    for (tn,) in existing_numbers:
        try:
            _, year, seq = tn.split("-")
            counters[int(year)] = max(counters[int(year)], int(seq))
        except Exception:
            continue

    for row_id, created_at in rows:
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except ValueError:
                created_at = datetime.utcnow()

        year = (created_at or datetime.utcnow()).year
        counters[year] += 1
        ticket_number = f"TKT-{year}-{counters[year]:06d}"

        conn.execute(
            text("""
                UPDATE support_tickets
                SET ticket_number = :tn
                WHERE id = :id
            """),
            {"tn": ticket_number, "id": row_id},
        )

    # 5️⃣ Create indexes AFTER backfill

    existing_indexes = {i["name"] for i in inspector.get_indexes("support_tickets")}

    # Normal indexes
    idx_map = {
        "ix_support_tickets_user_id": ["user_id"],
        "ix_support_tickets_order_id": ["order_id"],
        "ix_support_tickets_status": ["status"],
        "ix_support_tickets_created_at": ["created_at"],
    }

    for idx_name, cols in idx_map.items():
        if idx_name not in existing_indexes:
            op.create_index(idx_name, "support_tickets", cols)

    # UNIQUE ticket_number index
    if "ix_support_tickets_ticket_number" not in existing_indexes:
        if dialect == "postgresql":
            # Must run outside transaction
            op.execute("COMMIT")
            op.execute("""
                CREATE UNIQUE INDEX CONCURRENTLY
                ix_support_tickets_ticket_number
                ON support_tickets(ticket_number)
                WHERE ticket_number IS NOT NULL
            """)
        else:
            op.create_index(
                "ix_support_tickets_ticket_number",
                "support_tickets",
                ["ticket_number"],
                unique=True,
            )

    # 6️⃣ Create ticket_replies table
    if "ticket_replies" not in inspector.get_table_names():
        op.create_table(
            "ticket_replies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ticket_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("author_type", sa.String(10), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column(
                "image_urls",
                sa.dialects.postgresql.JSONB if dialect == "postgresql" else sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb") if dialect == "postgresql" else "[]",
            ),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        )

        op.create_index("ix_ticket_replies_ticket_id", "ticket_replies", ["ticket_id"])