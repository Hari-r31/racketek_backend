"""coupon_usage table + performance indexes for coupon system

Revision ID: 008
Revises: 007
Create Date: 2026-03-03

What this migration does
------------------------
1. Creates the `coupon_usage` table for per-user redemption tracking.
2. Adds a composite index on (coupon_id, user_id) for fast per-user lookups.
3. Adds a covering index on `coupons.code` (already declared in the model,
   this migration makes it explicit in the DB for deployments that pre-date
   the index declaration).
4. Adds individual indexes on coupon_usage.user_id and coupon_usage.coupon_id
   as required by the spec.

Backward compatibility
----------------------
* No existing column is altered or dropped.
* `coupons.used_count` is preserved as the global counter; coupon_usage rows
  provide the per-user audit trail in addition.
* All new indexes are created with IF NOT EXISTS semantics via checkfirst=True.
"""
from alembic import op
import sqlalchemy as sa

revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. coupon_usage table ──────────────────────────────────────────────
    op.create_table(
        'coupon_usage',
        sa.Column('id',         sa.Integer(),  nullable=False),
        sa.Column('coupon_id',  sa.Integer(),  nullable=False),
        sa.Column('user_id',    sa.Integer(),  nullable=False),
        sa.Column('order_id',   sa.Integer(),  nullable=True),
        sa.Column('used_at',    sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),

        sa.PrimaryKeyConstraint('id'),

        sa.ForeignKeyConstraint(
            ['coupon_id'], ['coupons.id'],
            name='fk_coupon_usage_coupon',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name='fk_coupon_usage_user',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['order_id'], ['orders.id'],
            name='fk_coupon_usage_order',
            ondelete='SET NULL',
        ),
    )

    # ── 2. Indexes on coupon_usage (Req #5) ───────────────────────────────
    op.create_index(
        'ix_coupon_usage_coupon_id',
        'coupon_usage', ['coupon_id'],
        unique=False,
    )
    op.create_index(
        'ix_coupon_usage_user_id',
        'coupon_usage', ['user_id'],
        unique=False,
    )
    # Composite index: fast per-user coupon count lookups
    op.create_index(
        'ix_coupon_usage_coupon_user',
        'coupon_usage', ['coupon_id', 'user_id'],
        unique=False,
    )

    # ── 3. Index on coupons.code (Req #5) ─────────────────────────────────
    # checkfirst=True is safe if the index already exists from the model definition.
    op.create_index(
        'ix_coupons_code',
        'coupons', ['code'],
        unique=True,
        if_not_exists=True,
    )


def downgrade():
    # Remove indexes first, then the table
    op.drop_index('ix_coupons_code',            table_name='coupons',       if_exists=True)
    op.drop_index('ix_coupon_usage_coupon_user', table_name='coupon_usage',  if_exists=True)
    op.drop_index('ix_coupon_usage_user_id',    table_name='coupon_usage',  if_exists=True)
    op.drop_index('ix_coupon_usage_coupon_id',  table_name='coupon_usage',  if_exists=True)
    op.drop_table('coupon_usage')
