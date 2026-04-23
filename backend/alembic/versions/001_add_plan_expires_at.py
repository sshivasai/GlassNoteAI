"""Add plan_expires_at to users table

Revision ID: 001_add_plan_expires_at
Revises: 
Create Date: 2026-04-21

"""
from alembic import op
import sqlalchemy as sa

revision = '001_add_plan_expires_at'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('plan_expires_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'plan_expires_at')
