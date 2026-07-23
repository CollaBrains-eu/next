"""create pending_registrations table

Revision ID: 440deb6610bb
Revises: f4e8b2a6c9d1
Create Date: 2026-07-23

Priority 3 commercial SaaS (ADR 0074): backs self-service signup. Purely
additive new table, safe on a live database.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "440deb6610bb"
down_revision = "f4e8b2a6c9d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_registrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("organization_name", sa.String(length=255), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pending_registrations_username", "pending_registrations", ["username"])
    op.create_index("ix_pending_registrations_token", "pending_registrations", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_pending_registrations_token", table_name="pending_registrations")
    op.drop_index("ix_pending_registrations_username", table_name="pending_registrations")
    op.drop_table("pending_registrations")
