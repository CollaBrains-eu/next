"""contact details

Revision ID: 5dd392e03c44
Revises: a1b2c3d4e5f6
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "5dd392e03c44"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_details",
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("po_box_address_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("visiting_address_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["po_box_address_entity_id"], ["entities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["visiting_address_entity_id"], ["entities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("entity_id"),
    )
    op.add_column("entity_relationships", sa.Column("title", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("entity_relationships", "title")
    op.drop_table("contact_details")
