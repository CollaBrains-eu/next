"""document correspondent address fields

Revision ID: c2e9f5a7b1d4
Revises: b7d3f9c1e5a2
Create Date: 2026-07-20

`correspondent` was a bare name string with no address -- extraction now
asks for the correspondent's street/house_number/po_box/postal_code/city/
country too, mirroring AddressDetail's field set/lengths.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2e9f5a7b1d4"
down_revision: Union[str, None] = "b7d3f9c1e5a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("correspondent_street", sa.String(255), nullable=True))
    op.add_column("documents", sa.Column("correspondent_house_number", sa.String(20), nullable=True))
    op.add_column("documents", sa.Column("correspondent_po_box", sa.String(20), nullable=True))
    op.add_column("documents", sa.Column("correspondent_postal_code", sa.String(20), nullable=True))
    op.add_column("documents", sa.Column("correspondent_city", sa.String(255), nullable=True))
    op.add_column("documents", sa.Column("correspondent_country", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "correspondent_country")
    op.drop_column("documents", "correspondent_city")
    op.drop_column("documents", "correspondent_postal_code")
    op.drop_column("documents", "correspondent_po_box")
    op.drop_column("documents", "correspondent_house_number")
    op.drop_column("documents", "correspondent_street")
