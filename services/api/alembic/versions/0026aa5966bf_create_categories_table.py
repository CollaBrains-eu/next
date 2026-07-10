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

# Inlined rather than imported from api.document_categories: migrations must
# not depend on application code, which can change after this revision is
# written (and, concretely, alembic resolves the revision graph -- including
# loading this file -- before env.py's src/ sys.path hack runs, so an
# `api.*` import here raises ModuleNotFoundError for any command that walks
# the graph, e.g. `alembic heads`/`upgrade head`).
DOCUMENT_CATEGORIES: list[dict] = [
    # -- Finance --
    {"slug": "finance", "icon": "Coins", "color": "#FF9500", "parent": None, "doc_types": []},
    {"slug": "payslip", "icon": "Banknote", "color": "#FF9500", "parent": "finance",
     "doc_types": ["payslip", "salary", "annual_statement"]},
    {"slug": "tax", "icon": "Landmark", "color": "#FF3B30", "parent": "finance", "doc_types": ["tax"]},
    {"slug": "pension_benefits", "icon": "PiggyBank", "color": "#FFCC00", "parent": "finance",
     "doc_types": ["pension", "benefits"]},
    {"slug": "bank_statement", "icon": "Building2", "color": "#34AADC", "parent": "finance",
     "doc_types": ["bank_statement", "bank"]},
    {"slug": "invoice", "icon": "Receipt", "color": "#FF3B30", "parent": "finance", "doc_types": ["invoice"]},
    {"slug": "guardianship", "icon": "Gavel", "color": "#FF9500", "parent": "finance",
     "doc_types": ["guardianship"]},

    # -- Housing & Vehicle --
    {"slug": "housing_vehicle", "icon": "Home", "color": "#34C759", "parent": None, "doc_types": []},
    {"slug": "mortgage_housing", "icon": "Home", "color": "#007AFF", "parent": "housing_vehicle",
     "doc_types": ["mortgage", "housing", "notarial"]},
    {"slug": "vehicle", "icon": "Car", "color": "#FF6B35", "parent": "housing_vehicle", "doc_types": ["vehicle"]},
    {"slug": "rental_contract", "icon": "Key", "color": "#34C759", "parent": "housing_vehicle", "doc_types": []},

    # -- Insurance & Care --
    {"slug": "insurance_care", "icon": "Shield", "color": "#4CD964", "parent": None, "doc_types": []},
    {"slug": "insurance", "icon": "Shield", "color": "#4CD964", "parent": "insurance_care",
     "doc_types": ["policy", "insurance"]},
    {"slug": "medical_care", "icon": "HeartPulse", "color": "#5AC8FA", "parent": "insurance_care",
     "doc_types": ["medical", "care"]},

    # -- Work & Education --
    {"slug": "work_education", "icon": "Briefcase", "color": "#5856D6", "parent": None, "doc_types": []},
    {"slug": "employment_contract", "icon": "FileText", "color": "#5856D6", "parent": "work_education",
     "doc_types": ["contract"]},
    {"slug": "education", "icon": "GraduationCap", "color": "#5856D6", "parent": "work_education",
     "doc_types": ["education"]},
    {"slug": "cv_references", "icon": "User", "color": "#5856D6", "parent": "work_education", "doc_types": ["cv"]},

    # -- Government & Identity --
    {"slug": "government_identity", "icon": "Shield", "color": "#8E8E93", "parent": None, "doc_types": []},
    {"slug": "government", "icon": "Landmark", "color": "#8E8E93", "parent": "government_identity",
     "doc_types": ["government"]},
    {"slug": "identity_document", "icon": "CreditCard", "color": "#8E8E93", "parent": "government_identity",
     "doc_types": ["identity_document"]},
    {"slug": "notarial", "icon": "Scale", "color": "#8E8E93", "parent": "government_identity", "doc_types": []},

    # -- Other --
    {"slug": "other_group", "icon": "Inbox", "color": "#8E8E93", "parent": None, "doc_types": []},
    {"slug": "correspondence", "icon": "Mail", "color": "#8E8E93", "parent": "other_group",
     "doc_types": ["correspondence"]},
    {"slug": "other_documents", "icon": "File", "color": "#8E8E93", "parent": "other_group",
     "doc_types": ["other", "legal"]},
]

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
    op.create_index('ix_documents_category_id', 'documents', ['category_id'])

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
    op.drop_index('ix_documents_category_id', table_name='documents')
    op.drop_column('documents', 'category_id')
    op.drop_table('categories')
