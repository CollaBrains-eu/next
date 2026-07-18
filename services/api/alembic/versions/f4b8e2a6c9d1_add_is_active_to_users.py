"""add is_active to users

Revision ID: f4b8e2a6c9d1
Revises: d3f8a1c6b9e4
Create Date: 2026-07-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f4b8e2a6c9d1'
down_revision: Union[str, None] = 'd3f8a1c6b9e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column('users', 'is_active')
