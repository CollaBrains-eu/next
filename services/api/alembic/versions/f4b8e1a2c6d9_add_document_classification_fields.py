"""add document classification fields

Revision ID: f4b8e1a2c6d9
Revises: a7d3f9c2b8e1
Create Date: 2026-07-09 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f4b8e1a2c6d9'
down_revision: Union[str, None] = 'a7d3f9c2b8e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('doc_type', sa.String(length=50), nullable=True))
    op.add_column(
        'documents',
        sa.Column('tags', sa.ARRAY(sa.String()), nullable=False, server_default='{}'),
    )
    op.add_column('documents', sa.Column('correspondent', sa.String(length=255), nullable=True))
    op.add_column('documents', sa.Column('classification_confidence', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'classification_confidence')
    op.drop_column('documents', 'correspondent')
    op.drop_column('documents', 'tags')
    op.drop_column('documents', 'doc_type')
