"""create organizations table and add organization_id to users

Revision ID: f2a9c6d8b1e4
Revises: e9c4b7a2f6d3
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f2a9c6d8b1e4'
down_revision: Union[str, None] = 'e9c4b7a2f6d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Must match api.models.DEFAULT_ORGANIZATION_ID.
DEFAULT_ORGANIZATION_ID = '00000000-0000-0000-0000-000000000001'


def upgrade() -> None:
    op.create_table('organizations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('policies', postgresql.JSONB(), server_default='{}', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )

    op.execute(
        "INSERT INTO organizations (id, name, policies) VALUES "
        f"('{DEFAULT_ORGANIZATION_ID}', 'Default Organization', '{{}}')"
    )

    # Add nullable first, backfill, then tighten to NOT NULL -- the safe
    # pattern for a required column on a live table with existing rows.
    # server_default means every pre-existing test/row that doesn't set
    # this explicitly still gets the default organization automatically.
    op.add_column(
        'users',
        sa.Column(
            'organization_id', sa.UUID(), nullable=True,
            server_default=sa.text(f"'{DEFAULT_ORGANIZATION_ID}'::uuid"),
        ),
    )
    op.execute(f"UPDATE users SET organization_id = '{DEFAULT_ORGANIZATION_ID}' WHERE organization_id IS NULL")
    op.alter_column('users', 'organization_id', nullable=False)
    op.create_foreign_key('fk_users_organization_id', 'users', 'organizations', ['organization_id'], ['id'])
    op.create_index('ix_users_organization_id', 'users', ['organization_id'])


def downgrade() -> None:
    op.drop_index('ix_users_organization_id', table_name='users')
    op.drop_constraint('fk_users_organization_id', 'users', type_='foreignkey')
    op.drop_column('users', 'organization_id')
    op.drop_table('organizations')
