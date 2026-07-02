"""create entities, entity_mentions, entity_relationships tables

Revision ID: e58c2a91f6d7
Revises: d29b6a4f0e11
Create Date: 2026-07-02 19:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e58c2a91f6d7'
down_revision: Union[str, None] = 'd29b6a4f0e11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('entities',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=500), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_entities_name', 'entities', ['name'])
    op.create_index('ix_entities_entity_type', 'entities', ['entity_type'])

    op.create_table('entity_mentions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('entity_id', 'document_id', name='uq_entity_mentions_entity_document')
    )
    op.create_index('ix_entity_mentions_document_id', 'entity_mentions', ['document_id'])

    op.create_table('entity_relationships',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('source_entity_id', sa.UUID(), nullable=False),
    sa.Column('target_entity_id', sa.UUID(), nullable=False),
    sa.Column('relationship_type', sa.String(length=255), nullable=False),
    sa.Column('document_id', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['source_entity_id'], ['entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['target_entity_id'], ['entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_entity_relationships_source_entity_id', 'entity_relationships', ['source_entity_id'])
    op.create_index('ix_entity_relationships_target_entity_id', 'entity_relationships', ['target_entity_id'])


def downgrade() -> None:
    op.drop_index('ix_entity_relationships_target_entity_id', table_name='entity_relationships')
    op.drop_index('ix_entity_relationships_source_entity_id', table_name='entity_relationships')
    op.drop_table('entity_relationships')
    op.drop_index('ix_entity_mentions_document_id', table_name='entity_mentions')
    op.drop_table('entity_mentions')
    op.drop_index('ix_entities_entity_type', table_name='entities')
    op.drop_index('ix_entities_name', table_name='entities')
    op.drop_table('entities')
