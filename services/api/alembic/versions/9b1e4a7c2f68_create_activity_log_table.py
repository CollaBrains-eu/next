"""create activity_log table

Revision ID: 9b1e4a7c2f68
Revises: 8aa5b9c764d2
Create Date: 2026-07-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '9b1e4a7c2f68'
down_revision: Union[str, None] = '8aa5b9c764d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('activity_log',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('entity_type', sa.String(length=20), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.Column('action', sa.String(length=50), nullable=False),
    sa.Column('actor_user_id', sa.UUID(), nullable=False),
    sa.Column('detail', postgresql.JSONB(), server_default='{}', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_activity_log_entity_id', 'activity_log', ['entity_id'])


def downgrade() -> None:
    op.drop_index('ix_activity_log_entity_id', table_name='activity_log')
    op.drop_table('activity_log')
