"""Add session_summary and conversation_json to sessions table

Revision ID: 003_add_sessions_columns
Revises: 002_add_plan_expires_at
Create Date: 2026-04-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003_add_sessions_columns'
down_revision = '002_add_plan_expires_at'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add session_summary column
    op.add_column(
        'sessions',
        sa.Column('session_summary', sa.Text(), nullable=True),
    )

    # Add conversation_json column
    op.add_column(
        'sessions',
        sa.Column('conversation_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('sessions', 'conversation_json')
    op.drop_column('sessions', 'session_summary')
