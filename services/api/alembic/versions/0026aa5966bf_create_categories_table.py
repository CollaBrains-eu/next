"""create categories table

Revision ID: 0026aa5966bf
Revises: d1a4e7f9c2b6
Create Date: 2026-07-10 00:00:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from api.document_categories import DOCUMENT_CATEGORIES

revision: str = '0026aa5966bf'
down_revision: Union[str, None] = 'd1a4e7f9c2b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'categories',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('category_type', sa.String(length=50), nullable=False),
        sa.Column('icon', sa.String(length=100), nullable=True),
        sa.Column('color', sa.String(length=50), nullable=True),
        sa.Column('parent_id', UUID(as_uuid=True), sa.ForeignKey('categories.id', ondelete='CASCADE'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('slug', 'category_type', name='uq_category_slug_type'),
    )
    op.add_column(
        'documents',
        sa.Column('category_id', UUID(as_uuid=True), sa.ForeignKey('categories.id', ondelete='SET NULL'), nullable=True),
    )

    categories_table = sa.table(
        'categories',
        sa.column('id', UUID(as_uuid=True)),
        sa.column('name', sa.String),
        sa.column('slug', sa.String),
        sa.column('category_type', sa.String),
        sa.column('icon', sa.String),
        sa.column('color', sa.String),
        sa.column('parent_id', UUID(as_uuid=True)),
    )

    slug_to_id: dict[str, uuid.UUID] = {cat["slug"]: uuid.uuid4() for cat in DOCUMENT_CATEGORIES}

    op.bulk_insert(
        categories_table,
        [
            {
                "id": slug_to_id[cat["slug"]],
                "name": cat["slug"],
                "slug": cat["slug"],
                "category_type": "document",
                "icon": cat["icon"],
                "color": cat["color"],
                "parent_id": slug_to_id[cat["parent"]] if cat["parent"] else None,
            }
            for cat in DOCUMENT_CATEGORIES
        ],
    )


def downgrade() -> None:
    op.drop_column('documents', 'category_id')
    op.drop_table('categories')
