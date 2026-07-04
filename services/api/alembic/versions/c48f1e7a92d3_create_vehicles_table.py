"""create vehicles table

Revision ID: c48f1e7a92d3
Revises: a3f7c9e2b5d8
Create Date: 2026-07-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c48f1e7a92d3'
down_revision: Union[str, None] = 'a3f7c9e2b5d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('vehicles',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.Column('kenteken', sa.String(length=20), nullable=True),
    sa.Column('vin', sa.String(length=17), nullable=True),
    sa.Column('voertuigsoort', sa.String(length=100), nullable=True),
    sa.Column('merk', sa.String(length=100), nullable=True),
    sa.Column('handelsbenaming', sa.String(length=100), nullable=True),
    sa.Column('eerste_kleur', sa.String(length=50), nullable=True),
    sa.Column('datum_eerste_toelating', sa.String(length=20), nullable=True),
    sa.Column('vervaldatum_apk', sa.String(length=20), nullable=True),
    sa.Column('wam_verzekerd', sa.String(length=10), nullable=True),
    sa.Column('openstaande_terugroepactie_indicator', sa.String(length=10), nullable=True),
    sa.Column('brandstofomschrijving', sa.String(length=100), nullable=True),
    sa.Column('massa_ledig_voertuig', sa.String(length=20), nullable=True),
    sa.Column('aantal_cilinders', sa.String(length=20), nullable=True),
    sa.Column('wielbasis', sa.String(length=20), nullable=True),
    sa.Column('catalogusprijs', sa.String(length=20), nullable=True),
    sa.Column('aantal_zitplaatsen', sa.String(length=20), nullable=True),
    sa.Column('aantal_deuren', sa.String(length=20), nullable=True),
    sa.Column('vermogen_massarijklaar', sa.String(length=20), nullable=True),
    sa.Column('lengte', sa.String(length=20), nullable=True),
    sa.Column('europese_voertuigcategorie', sa.String(length=20), nullable=True),
    sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('entity_id')
    )
    op.create_index('ix_vehicles_kenteken', 'vehicles', ['kenteken'])
    op.create_index('ix_vehicles_vin', 'vehicles', ['vin'])


def downgrade() -> None:
    op.drop_index('ix_vehicles_vin', table_name='vehicles')
    op.drop_index('ix_vehicles_kenteken', table_name='vehicles')
    op.drop_table('vehicles')
