"""add category to tasks (v2 parity: betaling/afspraak/deadline/melding)

Revision ID: e1a5c9f3b7d2
Revises: d8f4a2c6e1b9
Create Date: 2026-07-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1a5c9f3b7d2"
down_revision: Union[str, None] = "d8f4a2c6e1b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("category", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "category")
