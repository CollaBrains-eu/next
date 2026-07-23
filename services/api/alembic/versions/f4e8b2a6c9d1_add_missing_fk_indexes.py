"""add missing FK indexes (documents.residency_id, tasks.created_by)

Revision ID: f4e8b2a6c9d1
Revises: 5dd392e03c44
Create Date: 2026-07-23

ADR 0066 (audit) / ADR 0071 (Priority 2, item 5): spot-checking foreign
keys found these two had no index, unlike every sibling FK on the same
tables (documents.owner_id/case_id, tasks.document_id) -- filtering
documents by residency, or tasks by creator, was a sequential scan.
`documents.category_id` was also flagged by the original audit, but
re-checking while writing this migration found it's already indexed
(migration 0026aa5966bf, `create_categories_table`) -- the audit's grep
missed it; not re-added here. Purely additive (CREATE INDEX, no data
change), safe on a live table.
"""
from alembic import op

revision = "f4e8b2a6c9d1"
down_revision = "5dd392e03c44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_documents_residency_id", "documents", ["residency_id"])
    op.create_index("ix_tasks_created_by", "tasks", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_tasks_created_by", table_name="tasks")
    op.drop_index("ix_documents_residency_id", table_name="documents")
