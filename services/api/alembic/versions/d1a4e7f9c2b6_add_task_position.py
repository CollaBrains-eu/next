"""add position column to tasks for kanban board ordering

Revision ID: d1a4e7f9c2b6
Revises: c8f2a5e9d3b7
Create Date: 2026-07-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1a4e7f9c2b6'
down_revision: Union[str, None] = 'c8f2a5e9d3b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('position', sa.Integer(), nullable=False, server_default='0'))
    op.execute("""
        UPDATE tasks SET position = sub.rn - 1
        FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY status ORDER BY created_at) AS rn
            FROM tasks
        ) AS sub
        WHERE tasks.id = sub.id
    """)
    op.alter_column('tasks', 'position', server_default=None)


def downgrade() -> None:
    op.drop_column('tasks', 'position')
