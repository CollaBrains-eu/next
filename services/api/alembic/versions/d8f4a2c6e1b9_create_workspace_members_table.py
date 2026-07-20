"""create workspace_members table (whole-workspace sharing, v2 parity)

Revision ID: d8f4a2c6e1b9
Revises: c2e9f5a7b1d4
Create Date: 2026-07-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d8f4a2c6e1b9"
down_revision: Union[str, None] = "c2e9f5a7b1d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("can_export", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("owner_id", "member_id", name="uq_workspace_members_owner_member"),
    )
    op.create_index("ix_workspace_members_owner_id", "workspace_members", ["owner_id"])
    op.create_index("ix_workspace_members_member_id", "workspace_members", ["member_id"])


def downgrade() -> None:
    op.drop_index("ix_workspace_members_member_id", table_name="workspace_members")
    op.drop_index("ix_workspace_members_owner_id", table_name="workspace_members")
    op.drop_table("workspace_members")
