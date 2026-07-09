"""create user_facts table

Revision ID: c8f2a5e9d3b7
Revises: b3e7c9d1a4f6
Create Date: 2026-07-09 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c8f2a5e9d3b7'
down_revision: Union[str, None] = 'b3e7c9d1a4f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('user_facts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('fact_type', sa.String(length=100), nullable=False),
    sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('valid_from', sa.Date(), nullable=False),
    sa.Column('valid_to', sa.Date(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('source_document_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False, server_default='pending_review'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    sa.ForeignKeyConstraint(['source_document_id'], ['documents.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_facts_user_id_fact_type', 'user_facts', ['user_id', 'fact_type'])


def downgrade() -> None:
    op.drop_index('ix_user_facts_user_id_fact_type', table_name='user_facts')
    op.drop_table('user_facts')
