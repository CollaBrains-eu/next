"""add metafields to documents

Revision ID: 7c966d7eebf4
Revises: e1a5c9f3b7d2
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "7c966d7eebf4"
down_revision: Union[str, None] = "e1a5c9f3b7d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("metafields", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "metafields")
