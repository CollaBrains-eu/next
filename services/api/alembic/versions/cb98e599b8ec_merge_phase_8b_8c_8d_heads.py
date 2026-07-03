"""merge phase 8b/8c/8d heads

Revision ID: cb98e599b8ec
Revises: a1c8e5f3d9b2, b4f7a2c9d1e3, c7e2b9f4a1d6
Create Date: 2026-07-03 11:24:35.385756

"""
from typing import Sequence, Union


revision: str = 'cb98e599b8ec'
down_revision: Union[str, None] = ('a1c8e5f3d9b2', 'b4f7a2c9d1e3', 'c7e2b9f4a1d6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
