"""create invitations table, add pending_registrations.invitation_token

Revision ID: dce934efdabf
Revises: dfcaaab5d5f6
Create Date: 2026-07-23

Priority 3 commercial SaaS (ADR 0074): org invitations by email, for
inviting someone who isn't a provisioned platform user yet (unlike the
pre-existing case/workspace sharing, which both require the invitee to
already exist). Purely additive, safe on a live database.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "dce934efdabf"
down_revision = "dfcaaab5d5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("invited_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_invitations_organization_id", "invitations", ["organization_id"])
    op.create_index("ix_invitations_token", "invitations", ["token"], unique=True)

    op.add_column("pending_registrations", sa.Column("invitation_token", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("pending_registrations", "invitation_token")
    op.drop_index("ix_invitations_token", table_name="invitations")
    op.drop_index("ix_invitations_organization_id", table_name="invitations")
    op.drop_table("invitations")
