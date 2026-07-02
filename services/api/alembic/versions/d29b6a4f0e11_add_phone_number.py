"""add users.phone_number

Revision ID: d29b6a4f0e11
Revises: c1b8e3f9a204
Create Date: 2026-07-02 19:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd29b6a4f0e11'
down_revision: Union[str, None] = 'c1b8e3f9a204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('phone_number', sa.String(length=32), nullable=True))
    op.create_unique_constraint('uq_users_phone_number', 'users', ['phone_number'])


def downgrade() -> None:
    op.drop_constraint('uq_users_phone_number', 'users', type_='unique')
    op.drop_column('users', 'phone_number')
