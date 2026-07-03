"""create reflection_log table

Revision ID: a1c8e5f3d9b2
Revises: e58c2a91f6d7
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a1c8e5f3d9b2'
down_revision: Union[str, None] = 'e58c2a91f6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('reflection_log',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('endpoint', sa.String(length=255), nullable=False),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('sufficient_evidence', sa.Boolean(), nullable=False),
    sa.Column('confidence', sa.Integer(), nullable=False),
    sa.Column('issues', postgresql.JSONB(), server_default='[]', nullable=False),
    sa.Column('retried', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_reflection_log_user_id', 'reflection_log', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_reflection_log_user_id', table_name='reflection_log')
    op.drop_table('reflection_log')
