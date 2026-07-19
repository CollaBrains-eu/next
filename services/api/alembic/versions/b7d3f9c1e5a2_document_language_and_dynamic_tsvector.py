"""document language + drop content_tsv generated expression

Revision ID: b7d3f9c1e5a2
Revises: a4c8e1f6b3d7
Create Date: 2026-07-19

content_tsv was GENERATED ALWAYS AS (to_tsvector('english', content))
STORED -- hardcoded to English, mis-stemming German/Dutch content this
platform's own locale files (en/de/nl) say it supports. Postgres requires
a generated column's expression to be IMMUTABLE, which rules out looking
up a per-row regconfig from the parent document's detected language, so
this drops the generation expression (keeping each row's current stored
value) and makes content_tsv a plain column the ingestion pipeline now
populates explicitly with the right language's config (documents.py).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7d3f9c1e5a2"
down_revision: Union[str, None] = "a4c8e1f6b3d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("language", sa.String(20), nullable=True))
    op.execute("ALTER TABLE document_chunks ALTER COLUMN content_tsv DROP EXPRESSION")


def downgrade() -> None:
    op.execute("ALTER TABLE document_chunks DROP COLUMN content_tsv")
    op.add_column(
        "document_chunks",
        sa.Column(
            "content_tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', content)", persisted=True),
            nullable=True,
        ),
    )
    op.drop_column("documents", "language")
