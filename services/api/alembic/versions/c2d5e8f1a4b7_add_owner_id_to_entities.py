"""add owner_id to entities (per-account entity/vehicle graph, Phase 28)

Revision ID: c2d5e8f1a4b7
Revises: 1a9b3c5d7e2f
Create Date: 2026-07-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c2d5e8f1a4b7'
down_revision: Union[str, None] = '1a9b3c5d7e2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('entities', sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=True))

    # Backfill from whichever document first mentioned each entity -- that
    # document's owner is the account this entity should belong to now that
    # entities are per-account instead of system-wide.
    op.execute(
        """
        UPDATE entities e
        SET owner_id = sub.owner_id
        FROM (
            SELECT DISTINCT ON (em.entity_id) em.entity_id, d.owner_id
            FROM entity_mentions em
            JOIN documents d ON d.id = em.document_id
            ORDER BY em.entity_id, em.created_at ASC
        ) sub
        WHERE e.id = sub.entity_id
        """
    )

    # Entities with no mention at all (impossible via extraction, but manual
    # creation existed briefly with no owner concept) can't be attributed to
    # anyone -- there's no legitimate account to assign them to, so drop them
    # rather than leave orphaned rows a NOT NULL constraint can't allow.
    op.execute("DELETE FROM entities WHERE owner_id IS NULL")

    op.alter_column('entities', 'owner_id', nullable=False)
    op.create_foreign_key(
        'entities_owner_id_fkey', 'entities', 'users', ['owner_id'], ['id'], ondelete='CASCADE'
    )
    op.create_index('ix_entities_owner_id', 'entities', ['owner_id'])


def downgrade() -> None:
    op.drop_index('ix_entities_owner_id', table_name='entities')
    op.drop_constraint('entities_owner_id_fkey', 'entities', type_='foreignkey')
    op.drop_column('entities', 'owner_id')
