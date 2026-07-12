"""create case_members table (shared case access, Phase 26)

Revision ID: f7c3a8e2b5d1
Revises: e1b7f4a9c2d8
Create Date: 2026-07-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f7c3a8e2b5d1"
down_revision: Union[str, None] = "e1b7f4a9c2d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "case_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("case_id", "user_id", name="uq_case_members_case_user"),
    )
    op.create_index("ix_case_members_case_id", "case_members", ["case_id"])
    op.create_index("ix_case_members_user_id", "case_members", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_case_members_user_id", table_name="case_members")
    op.drop_index("ix_case_members_case_id", table_name="case_members")
    op.drop_table("case_members")
