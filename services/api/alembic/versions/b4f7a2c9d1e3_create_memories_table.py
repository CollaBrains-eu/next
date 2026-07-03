"""create memories table

Revision ID: b4f7a2c9d1e3
Revises: e58c2a91f6d7
Create Date: 2026-07-03 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from sqlalchemy.dialects import postgresql


revision: str = 'b4f7a2c9d1e3'
down_revision: Union[str, None] = 'e58c2a91f6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('memories',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('memory_type', sa.String(length=50), nullable=False),
    sa.Column('importance', sa.Integer(), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('embedding', Vector(768), nullable=False),
    sa.Column('json_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_memories_user_id', 'memories', ['user_id'])
    op.execute(
        'CREATE INDEX ix_memories_embedding_hnsw ON memories '
        'USING hnsw (embedding vector_cosine_ops)'
    )


def downgrade() -> None:
    op.drop_index('ix_memories_embedding_hnsw', table_name='memories')
    op.drop_index('ix_memories_user_id', table_name='memories')
    op.drop_table('memories')
