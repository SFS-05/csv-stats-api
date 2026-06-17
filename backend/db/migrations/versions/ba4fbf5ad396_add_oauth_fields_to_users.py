"""add_oauth_fields_to_users

Revision ID: ba4fbf5ad396
Revises: 
Create Date: 2026-06-16 16:52:31.123332

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba4fbf5ad396'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns nullable first, backfill, then enforce NOT NULL
    op.add_column('users', sa.Column('google_id', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.String(length=512), nullable=True))
    op.add_column('users', sa.Column('auth_provider', sa.String(length=50), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE users SET auth_provider = 'local' WHERE auth_provider IS NULL")
    op.alter_column('users', 'auth_provider', existing_type=sa.String(length=50), nullable=False)
    op.alter_column('users', 'hashed_password',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
    op.create_index(op.f('ix_users_google_id'), 'users', ['google_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_google_id'), table_name='users')
    op.alter_column('users', 'hashed_password',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'auth_provider')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'google_id')
