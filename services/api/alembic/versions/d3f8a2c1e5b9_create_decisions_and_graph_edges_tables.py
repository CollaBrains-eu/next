"""create decisions and graph_edges tables

Revision ID: d3f8a2c1e5b9
Revises: cb98e599b8ec
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd3f8a2c1e5b9'
down_revision: Union[str, None] = 'cb98e599b8ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('decisions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('plan_id', sa.UUID(), nullable=True),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_decisions_user_id', 'decisions', ['user_id'])

    op.create_table('graph_edges',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('source_type', sa.String(length=50), nullable=False),
    sa.Column('source_id', sa.UUID(), nullable=False),
    sa.Column('target_type', sa.String(length=50), nullable=False),
    sa.Column('target_id', sa.UUID(), nullable=False),
    sa.Column('relationship_type', sa.String(length=50), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_graph_edges_source', 'graph_edges', ['source_type', 'source_id'])
    op.create_index('ix_graph_edges_target', 'graph_edges', ['target_type', 'target_id'])


def downgrade() -> None:
    op.drop_index('ix_graph_edges_target', table_name='graph_edges')
    op.drop_index('ix_graph_edges_source', table_name='graph_edges')
    op.drop_table('graph_edges')
    op.drop_index('ix_decisions_user_id', table_name='decisions')
    op.drop_table('decisions')
