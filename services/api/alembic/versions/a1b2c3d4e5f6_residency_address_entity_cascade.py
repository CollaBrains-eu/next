"""residency address_entity_id cascade delete

Revision ID: a1b2c3d4e5f6
Revises: c4d7f2a9e1b3
Create Date: 2026-07-23

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'c4d7f2a9e1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('residencies_address_entity_id_fkey', 'residencies', type_='foreignkey')
    op.create_foreign_key(
        'residencies_address_entity_id_fkey', 'residencies', 'entities',
        ['address_entity_id'], ['id'], ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('residencies_address_entity_id_fkey', 'residencies', type_='foreignkey')
    op.create_foreign_key(
        'residencies_address_entity_id_fkey', 'residencies', 'entities',
        ['address_entity_id'], ['id'],
    )
