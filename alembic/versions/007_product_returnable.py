"""add is_returnable and return_window_days to products

Revision ID: 007
Revises: 006_users_profile_fields
Create Date: 2026-03-03

"""
from alembic import op
import sqlalchemy as sa

revision = '007'
down_revision = '006_users_profile_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'products',
        sa.Column('is_returnable', sa.Boolean(), nullable=False, server_default='true')
    )
    op.add_column(
        'products',
        sa.Column('return_window_days', sa.Integer(), nullable=False, server_default='7')
    )


def downgrade():
    op.drop_column('products', 'return_window_days')
    op.drop_column('products', 'is_returnable')
