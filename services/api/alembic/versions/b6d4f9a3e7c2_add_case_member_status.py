"""add case_members.status (invitation accept/decline, Phase 26b)

Revision ID: b6d4f9a3e7c2
Revises: a2e9d5c8f1b6
Create Date: 2026-07-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6d4f9a3e7c2"
down_revision: Union[str, None] = "a2e9d5c8f1b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "case_members",
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
    )
    # Rows created before this invitation flow existed were already-granted
    # access, not open invitations -- treat them as accepted, not pending.
    op.execute("UPDATE case_members SET status = 'accepted'")
    # Normalize the one pre-existing free-text role value into the new
    # fixed worker/member vocabulary.
    op.execute("UPDATE case_members SET role = 'worker' WHERE role = 'aannemer'")


def downgrade() -> None:
    op.drop_column("case_members", "status")
