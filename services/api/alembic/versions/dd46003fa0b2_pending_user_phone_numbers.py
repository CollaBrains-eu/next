"""pending user phone numbers + phone_prompt_dismissed

Revision ID: dd46003fa0b2
Revises: 0026aa5966bf
Create Date: 2026-07-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'dd46003fa0b2'
down_revision: Union[str, None] = '0026aa5966bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pending_user_phone_numbers',
        sa.Column('username', sa.String(255), primary_key=True),
        sa.Column('phone_number', sa.String(32), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column(
        'users',
        sa.Column('phone_prompt_dismissed', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('users', 'phone_prompt_dismissed')
    op.drop_table('pending_user_phone_numbers')
