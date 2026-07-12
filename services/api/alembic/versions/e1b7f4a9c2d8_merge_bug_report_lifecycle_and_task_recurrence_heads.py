"""merge bug_report_lifecycle and task_recurrence heads

Revision ID: e1b7f4a9c2d8
Revises: bb7a8fb6baa3, d4f8b2c6e9a1
Create Date: 2026-07-12
"""
from typing import Sequence, Union

revision: str = "e1b7f4a9c2d8"
down_revision: Union[str, None] = ("bb7a8fb6baa3", "d4f8b2c6e9a1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
