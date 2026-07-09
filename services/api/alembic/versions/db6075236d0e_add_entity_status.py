"""add entity status

Revision ID: db6075236d0e
Revises: c48f1e7a92d3
Create Date: 2026-07-09 00:49:35.311985

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'db6075236d0e'
down_revision: Union[str, None] = 'c48f1e7a92d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'entities',
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending_review'),
    )
    # Every entity that existed before this migration is already relied on
    # throughout the app (case linking, the entity graph, search) -- treat
    # all of them as already-reviewed so nothing currently visible
    # disappears behind the new review gate.
    op.execute("UPDATE entities SET status = 'confirmed'")


def downgrade() -> None:
    op.drop_column('entities', 'status')
