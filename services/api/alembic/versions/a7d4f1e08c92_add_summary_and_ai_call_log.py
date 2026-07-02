"""add documents.summary and ai_call_log table

Revision ID: a7d4f1e08c92
Revises: f3a91c7d2b44
Create Date: 2026-07-02 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7d4f1e08c92'
down_revision: Union[str, None] = 'f3a91c7d2b44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('summary', sa.Text(), nullable=True))

    op.create_table('ai_call_log',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('endpoint', sa.String(length=255), nullable=False),
    sa.Column('model', sa.String(length=255), nullable=False),
    sa.Column('prompt_tokens', sa.Integer(), nullable=True),
    sa.Column('completion_tokens', sa.Integer(), nullable=True),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_ai_call_log_user_id', 'ai_call_log', ['user_id'])
    op.create_index('ix_ai_call_log_created_at', 'ai_call_log', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_ai_call_log_created_at', table_name='ai_call_log')
    op.drop_index('ix_ai_call_log_user_id', table_name='ai_call_log')
    op.drop_table('ai_call_log')
    op.drop_column('documents', 'summary')
