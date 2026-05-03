"""Add byok_enabled column and migrate BYOK users

Revision ID: 004_add_byok_enabled
Revises: 003_add_sessions_columns
Create Date: 2026-05-01

"""
from alembic import op
import sqlalchemy as sa

revision = '004_add_byok_enabled'
down_revision = '003_add_sessions_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add byok_enabled column
    op.add_column(
        'users',
        sa.Column('byok_enabled', sa.Boolean(), nullable=False, server_default='false'),
    )

    # Migrate existing BYOK users (preserve their access)
    op.execute("""
        UPDATE users
        SET byok_enabled = TRUE
        WHERE plan = 'byok'
    """)

    # Move BYOK users to Free plan (they share same lifetime quota)
    op.execute("""
        UPDATE users
        SET plan = 'free'
        WHERE plan = 'byok'
    """)


def downgrade() -> None:
    # Restore BYOK users to byok plan
    op.execute("""
        UPDATE users
        SET plan = 'byok'
        WHERE byok_enabled = TRUE AND plan = 'free'
    """)

    # Drop byok_enabled column
    op.drop_column('users', 'byok_enabled')
