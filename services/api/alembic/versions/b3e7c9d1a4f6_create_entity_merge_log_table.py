"""create entity_merge_log table

Revision ID: b3e7c9d1a4f6
Revises: f4b8e1a2c6d9
Create Date: 2026-07-09 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3e7c9d1a4f6'
down_revision: Union[str, None] = 'f4b8e1a2c6d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('entity_merge_log',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('source_entity_id', sa.UUID(), nullable=False),
    sa.Column('target_entity_id', sa.UUID(), nullable=False),
    sa.Column('merged_by', sa.UUID(), nullable=False),
    sa.Column('merged_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['target_entity_id'], ['entities.id']),
    sa.ForeignKeyConstraint(['merged_by'], ['users.id']),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('entity_merge_log')
