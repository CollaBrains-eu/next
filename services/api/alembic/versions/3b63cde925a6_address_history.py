"""address history: address_details, residencies, documents.residency_id

Revision ID: 3b63cde925a6
Revises: dd46003fa0b2
Create Date: 2026-07-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "3b63cde925a6"
down_revision: Union[str, None] = "dd46003fa0b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "address_details",
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("street", sa.String(255), nullable=True),
        sa.Column("house_number", sa.String(20), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("city", sa.String(255), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("normalized_key", sa.String(255), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_address_details_normalized_key", "address_details", ["normalized_key"])

    op.create_table(
        "residencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("address_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending_review"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["address_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
    )
    # At most one "current" (valid_to IS NULL) residency per user -- enforced
    # at the DB level, not just application logic.
    op.create_index(
        "uq_residencies_current_per_user",
        "residencies",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL"),
    )

    op.add_column(
        "documents",
        sa.Column("residency_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_documents_residency_id", "documents", "residencies", ["residency_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_documents_residency_id", "documents", type_="foreignkey")
    op.drop_column("documents", "residency_id")
    op.drop_index("uq_residencies_current_per_user", table_name="residencies")
    op.drop_table("residencies")
    op.drop_index("ix_address_details_normalized_key", table_name="address_details")
    op.drop_table("address_details")
