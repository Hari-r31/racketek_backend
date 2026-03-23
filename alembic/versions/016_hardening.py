"""
Migration 016 — Production hardening

Changes:
  users table:
    ADD auth_provider                VARCHAR(20) NOT NULL DEFAULT 'local'
    ADD email_marketing_consent      BOOLEAN NOT NULL DEFAULT false
    ADD last_abandoned_cart_email_at TIMESTAMP NULL

  New table: inventory_reservations
    Holds stock reservations between order placement and payment.
    Replaces the old immediate stock deduction at order placement.

  New indexes (M3 FIX — dashboard/analytics query speed):
    orders.created_at  (already exists in some installs, created with IF NOT EXISTS)
    orders.status

Revision ID: 016
Revises:     015
"""
from alembic import op
import sqlalchemy as sa

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade():
    # ── users: auth_provider ──────────────────────────────────────────────
    op.add_column(
        "users",
        sa.Column(
            "auth_provider",
            sa.String(20),
            nullable=False,
            server_default="local",
        ),
    )

    # ── users: email marketing consent (H5) ───────────────────────────────
    op.add_column(
        "users",
        sa.Column(
            "email_marketing_consent",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "last_abandoned_cart_email_at",
            sa.DateTime(),
            nullable=True,
        ),
    )

    # ── inventory_reservations table (C5) ─────────────────────────────────
    op.create_table(
        "inventory_reservations",
        sa.Column("id",         sa.Integer(),    primary_key=True),
        sa.Column("order_id",   sa.Integer(),    sa.ForeignKey("orders.id",           ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer(),    sa.ForeignKey("products.id",         ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", sa.Integer(),    sa.ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("quantity",   sa.Integer(),    nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "confirmed", "released", name="reservationstatus"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_inv_res_order_id",   "inventory_reservations", ["order_id"])
    op.create_index("ix_inv_res_product_id", "inventory_reservations", ["product_id"])
    op.create_index("ix_inv_res_status",     "inventory_reservations", ["status"])
    op.create_index("ix_inv_res_expires_at", "inventory_reservations", ["expires_at"])

    # ── performance indexes (M3) ──────────────────────────────────────────
    # Use IF NOT EXISTS equivalent — catch already-existing indexes gracefully.
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_order_indexes = {idx["name"] for idx in inspector.get_indexes("orders")}

    if "ix_orders_created_at" not in existing_order_indexes:
        op.create_index("ix_orders_created_at", "orders", ["created_at"])
    if "ix_orders_status" not in existing_order_indexes:
        op.create_index("ix_orders_status", "orders", ["status"])


def downgrade():
    op.drop_index("ix_orders_status",        table_name="orders")
    op.drop_index("ix_orders_created_at",    table_name="orders")
    op.drop_index("ix_inv_res_expires_at",   table_name="inventory_reservations")
    op.drop_index("ix_inv_res_status",       table_name="inventory_reservations")
    op.drop_index("ix_inv_res_product_id",   table_name="inventory_reservations")
    op.drop_index("ix_inv_res_order_id",     table_name="inventory_reservations")
    op.drop_table("inventory_reservations")
    op.execute("DROP TYPE IF EXISTS reservationstatus")
    op.drop_column("users", "last_abandoned_cart_email_at")
    op.drop_column("users", "email_marketing_consent")
    op.drop_column("users", "auth_provider")
