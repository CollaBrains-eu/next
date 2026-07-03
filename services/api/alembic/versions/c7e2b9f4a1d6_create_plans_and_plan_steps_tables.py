"""create plans and plan_steps tables

Revision ID: c7e2b9f4a1d6
Revises: e58c2a91f6d7
Create Date: 2026-07-03 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects import postgresql


revision: str = 'c7e2b9f4a1d6'
down_revision: Union[str, None] = 'e58c2a91f6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('plans',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('goal_type', sa.String(length=50), nullable=False),
    sa.Column('goal_params', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('requires_approval', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_plans_user_id', 'plans', ['user_id'])

    op.create_table('plan_steps',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('plan_id', sa.UUID(), nullable=False),
    sa.Column('step_index', sa.Integer(), nullable=False),
    sa.Column('agent', sa.String(length=50), nullable=False),
    sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('result_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_plan_steps_plan_id', 'plan_steps', ['plan_id'])


def downgrade() -> None:
    op.drop_index('ix_plan_steps_plan_id', table_name='plan_steps')
    op.drop_table('plan_steps')
    op.drop_index('ix_plans_user_id', table_name='plans')
    op.drop_table('plans')
