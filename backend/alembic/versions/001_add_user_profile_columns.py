"""Add user profile and Google OAuth columns

Revision ID: 001_add_user_profile_columns
Revises:
Create Date: 2026-04-21

"""
from alembic import op
import sqlalchemy as sa

revision = '001_add_user_profile_columns'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add profile columns
    op.add_column(
        'users',
        sa.Column('first_name', sa.String(100), nullable=False, server_default=''),
    )
    op.add_column(
        'users',
        sa.Column('last_name', sa.String(100), nullable=False, server_default=''),
    )

    # Add OAuth columns
    op.add_column(
        'users',
        sa.Column('auth_provider', sa.String(20), nullable=False, server_default='email'),
    )
    op.add_column(
        'users',
        sa.Column('google_id', sa.String(255), nullable=True),
    )

    # Add index for google_id
    op.create_index('idx_users_google_id', 'users', ['google_id'], unique=False)

    # Add unique constraint for google_id
    op.create_unique_constraint('uq_users_google_id', 'users', ['google_id'])


def downgrade() -> None:
    op.drop_constraint('uq_users_google_id', 'users', type_='unique')
    op.drop_index('idx_users_google_id', table_name='users')
    op.drop_column('users', 'google_id')
    op.drop_column('users', 'auth_provider')
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')
