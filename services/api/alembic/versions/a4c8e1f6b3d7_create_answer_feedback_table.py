"""create answer_feedback table (Phase 28, answer-quality signal)

Revision ID: a4c8e1f6b3d7
Revises: f4b8e2a6c9d1
Create Date: 2026-07-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4c8e1f6b3d7"
down_revision: Union[str, None] = "f4b8e2a6c9d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "answer_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("endpoint", sa.String(50), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("rating", sa.String(10), nullable=False),
        sa.Column("reflection_confidence", sa.Integer(), nullable=True),
        sa.Column("reflection_sufficient_evidence", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_answer_feedback_user_id", "answer_feedback", ["user_id"])
    op.create_index("ix_answer_feedback_rating", "answer_feedback", ["rating"])


def downgrade() -> None:
    op.drop_index("ix_answer_feedback_rating", table_name="answer_feedback")
    op.drop_index("ix_answer_feedback_user_id", table_name="answer_feedback")
    op.drop_table("answer_feedback")
