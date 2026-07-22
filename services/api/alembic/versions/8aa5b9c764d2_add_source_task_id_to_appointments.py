"""add source_task_id to appointments

Revision ID: 8aa5b9c764d2
Revises: 7c966d7eebf4
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8aa5b9c764d2"
down_revision: Union[str, None] = "7c966d7eebf4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("source_task_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_appointments_source_task_id", "appointments", "tasks", ["source_task_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_appointments_source_task_id", "appointments", type_="foreignkey")
    op.drop_column("appointments", "source_task_id")
