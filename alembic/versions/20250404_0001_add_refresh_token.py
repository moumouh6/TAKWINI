"""Add refresh token columns to users table

Revision ID: 0001
Revises:
Create Date: 2025-04-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add refresh_token column
    op.add_column('users', sa.Column('refresh_token', sa.String(), nullable=True))
    op.create_index('ix_users_refresh_token', 'users', ['refresh_token'], unique=True)

    # Add refresh_token_expires column
    op.add_column('users', sa.Column('refresh_token_expires', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove columns in reverse order
    op.drop_column('users', 'refresh_token_expires')
    op.drop_index('ix_users_refresh_token', table_name='users')
    op.drop_column('users', 'refresh_token')
