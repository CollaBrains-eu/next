"""add date_format and time_format to user_preferences

Revision ID: 1a9b3c5d7e2f
Revises: b6d4f9a3e7c2
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1a9b3c5d7e2f'
down_revision: Union[str, None] = 'b6d4f9a3e7c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user_preferences', sa.Column('date_format', sa.String(length=10), nullable=True))
    op.add_column('user_preferences', sa.Column('time_format', sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column('user_preferences', 'time_format')
    op.drop_column('user_preferences', 'date_format')
