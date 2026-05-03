"""Add plan_expires_at to users table

Revision ID: 002_add_plan_expires_at
Revises: 001_add_user_profile_columns
Create Date: 2026-04-21

"""
from alembic import op
import sqlalchemy as sa

revision = '002_add_plan_expires_at'
down_revision = '001_add_user_profile_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('plan_expires_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'plan_expires_at')
