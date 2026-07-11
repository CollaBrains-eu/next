"""add task recurrence_rule and notified_at

Revision ID: bb7a8fb6baa3
Revises: 3b63cde925a6
Create Date: 2026-07-11 22:11:17.949873

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'bb7a8fb6baa3'
down_revision: Union[str, None] = '3b63cde925a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('recurrence_rule', sa.String(length=20), nullable=True))
    op.add_column('tasks', sa.Column('notified_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('tasks', 'notified_at')
    op.drop_column('tasks', 'recurrence_rule')
