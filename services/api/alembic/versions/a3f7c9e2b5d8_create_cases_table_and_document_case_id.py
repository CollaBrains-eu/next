"""create cases table and document case_id

Revision ID: a3f7c9e2b5d8
Revises: f2a9c6d8b1e4
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3f7c9e2b5d8'
down_revision: Union[str, None] = 'f2a9c6d8b1e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('cases',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=500), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=False, server_default='open'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_cases_user_id', 'cases', ['user_id'])

    op.add_column('documents', sa.Column('case_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_documents_case_id', 'documents', 'cases', ['case_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_documents_case_id', 'documents', ['case_id'])


def downgrade() -> None:
    op.drop_index('ix_documents_case_id', table_name='documents')
    op.drop_constraint('fk_documents_case_id', 'documents', type_='foreignkey')
    op.drop_column('documents', 'case_id')
    op.drop_index('ix_cases_user_id', table_name='cases')
    op.drop_table('cases')
