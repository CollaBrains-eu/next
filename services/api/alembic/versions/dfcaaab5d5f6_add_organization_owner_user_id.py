"""add organizations.owner_user_id

Revision ID: dfcaaab5d5f6
Revises: 440deb6610bb
Create Date: 2026-07-23

Priority 3 commercial SaaS (ADR 0074): a narrow "can manage this org"
permission, deliberately separate from the platform-wide User.role, so a
self-service signup's new Organization has a real owner without granting
that user the LDAP-wide Admin Dashboard. Nullable/no backfill -- existing
orgs (including DEFAULT_ORGANIZATION_ID) keep relying on platform admins,
same as before this migration. Purely additive, safe on a live table.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "dfcaaab5d5f6"
down_revision = "440deb6610bb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_organizations_owner_user_id_users",
        "organizations",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_organizations_owner_user_id_users", "organizations", type_="foreignkey")
    op.drop_column("organizations", "owner_user_id")
