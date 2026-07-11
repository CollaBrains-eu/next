"""bug_reports: v2 lifecycle fields (title/page_url/AI-triage/Codeberg/clarifying-Q&A)

Revision ID: d4f8b2c6e9a1
Revises: a7e3c9f21b06
Create Date: 2026-07-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f8b2c6e9a1"
down_revision: Union[str, None] = "a7e3c9f21b06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bug_reports", sa.Column("title", sa.String(200), nullable=True))
    op.add_column("bug_reports", sa.Column("page_url", sa.String(500), nullable=True))
    op.add_column("bug_reports", sa.Column("ai_labels", sa.Text(), nullable=True))
    op.add_column("bug_reports", sa.Column("ai_priority", sa.String(20), nullable=True))
    op.add_column("bug_reports", sa.Column("ai_suggested_fix", sa.Text(), nullable=True))
    op.add_column("bug_reports", sa.Column("codeberg_issue_url", sa.String(500), nullable=True))
    op.add_column("bug_reports", sa.Column("codeberg_issue_number", sa.Integer(), nullable=True))
    op.add_column("bug_reports", sa.Column("clarifying_questions", sa.Text(), nullable=True))
    op.add_column("bug_reports", sa.Column("clarifying_answers", sa.Text(), nullable=True))
    op.add_column("bug_reports", sa.Column("clarifying_status", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("bug_reports", "clarifying_status")
    op.drop_column("bug_reports", "clarifying_answers")
    op.drop_column("bug_reports", "clarifying_questions")
    op.drop_column("bug_reports", "codeberg_issue_number")
    op.drop_column("bug_reports", "codeberg_issue_url")
    op.drop_column("bug_reports", "ai_suggested_fix")
    op.drop_column("bug_reports", "ai_priority")
    op.drop_column("bug_reports", "ai_labels")
    op.drop_column("bug_reports", "page_url")
    op.drop_column("bug_reports", "title")
