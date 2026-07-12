"""create onboarding_tokens table (Phase 27, welcome email)

Revision ID: a2e9d5c8f1b6
Revises: f7c3a8e2b5d1
Create Date: 2026-07-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a2e9d5c8f1b6"
down_revision: Union[str, None] = "f7c3a8e2b5d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "onboarding_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token", name="uq_onboarding_tokens_token"),
    )
    op.create_index("ix_onboarding_tokens_token", "onboarding_tokens", ["token"])


def downgrade() -> None:
    op.drop_index("ix_onboarding_tokens_token", table_name="onboarding_tokens")
    op.drop_table("onboarding_tokens")
