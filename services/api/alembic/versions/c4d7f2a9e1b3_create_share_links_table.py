"""create share_links table

Revision ID: c4d7f2a9e1b3
Revises: 9b1e4a7c2f68
Create Date: 2026-07-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4d7f2a9e1b3'
down_revision: Union[str, None] = '9b1e4a7c2f68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('share_links',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('entity_type', sa.String(length=20), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.Column('token', sa.String(length=64), nullable=False),
    sa.Column('created_by_user_id', sa.UUID(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('entity_type', 'entity_id', name='uq_share_links_entity'),
    sa.UniqueConstraint('token')
    )
    op.create_index('ix_share_links_token', 'share_links', ['token'])


def downgrade() -> None:
    op.drop_index('ix_share_links_token', table_name='share_links')
    op.drop_table('share_links')
