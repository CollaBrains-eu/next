"""create documents and document_chunks tables

Revision ID: f3a91c7d2b44
Revises: c92c18f25b1e
Create Date: 2026-07-02 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from sqlalchemy.dialects import postgresql


revision: str = 'f3a91c7d2b44'
down_revision: Union[str, None] = 'c92c18f25b1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    op.create_table('documents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('owner_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('filename', sa.String(length=500), nullable=False),
    sa.Column('mime_type', sa.String(length=255), nullable=False),
    sa.Column('paperless_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('ocr_text', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_documents_owner_id', 'documents', ['owner_id'])
    op.create_index('ix_documents_status', 'documents', ['status'])

    op.create_table('document_chunks',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('embedding', Vector(768), nullable=False),
    sa.Column('content_tsv', postgresql.TSVECTOR(), sa.Computed("to_tsvector('english', content)", persisted=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_document_chunks_document_id', 'document_chunks', ['document_id'])
    op.create_index(
        'ix_document_chunks_content_tsv', 'document_chunks', ['content_tsv'], postgresql_using='gin'
    )
    op.execute(
        'CREATE INDEX ix_document_chunks_embedding_hnsw ON document_chunks '
        'USING hnsw (embedding vector_cosine_ops)'
    )


def downgrade() -> None:
    op.drop_index('ix_document_chunks_embedding_hnsw', table_name='document_chunks')
    op.drop_index('ix_document_chunks_content_tsv', table_name='document_chunks')
    op.drop_index('ix_document_chunks_document_id', table_name='document_chunks')
    op.drop_table('document_chunks')
    op.drop_index('ix_documents_status', table_name='documents')
    op.drop_index('ix_documents_owner_id', table_name='documents')
    op.drop_table('documents')
    op.execute('DROP EXTENSION IF EXISTS vector')
