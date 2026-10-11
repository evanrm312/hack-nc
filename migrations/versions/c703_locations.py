"""Sourced meeting metadata, private temporary locations and service meetings."""
from alembic import op
import sqlalchemy as sa
revision = 'c703locations'
down_revision = 'c702notifications'
branch_labels = depends_on = None

def upgrade():
    with op.batch_alter_table('meeting_spots') as b:
        for col in [sa.Column('latitude',sa.Float()),sa.Column('longitude',sa.Float()),
            sa.Column('coordinate_source',sa.Text()),sa.Column('safety_attributes',sa.JSON()),
            sa.Column('safety_source',sa.Text()),sa.Column('safety_checked_at',sa.String(10))]: b.add_column(col)
    with op.batch_alter_table('profiles') as b:
        b.add_column(sa.Column('preferred_meeting_spot_id',sa.String(32)))
        b.create_foreign_key('fk_profile_preferred_spot','meeting_spots',['preferred_meeting_spot_id'],['id'])
    with op.batch_alter_table('offer_revisions') as b:
        b.add_column(sa.Column('service_delivery',sa.String(16)))
        b.add_column(sa.Column('service_meeting_spot_id',sa.String(32)))
        b.create_foreign_key('fk_service_meeting_spot','meeting_spots',['service_meeting_spot_id'],['id'])
    op.create_table('exchange_locations',sa.Column('id',sa.String(32),primary_key=True),
        sa.Column('exchange_id',sa.String(32),sa.ForeignKey('exchanges.id'),nullable=False),
        sa.Column('participant_id',sa.String(32),sa.ForeignKey('profiles.id'),nullable=False),
        sa.Column('landmark',sa.String(120)),sa.Column('latitude',sa.Float()),sa.Column('longitude',sa.Float()),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('exchange_id','participant_id',name='uq_exchange_location_participant'))
    op.create_index('ix_exchange_locations_exchange_id','exchange_locations',['exchange_id'])

def downgrade():
    op.drop_table('exchange_locations')
    with op.batch_alter_table('offer_revisions') as b:
        b.drop_constraint('fk_service_meeting_spot',type_='foreignkey')
        b.drop_column('service_delivery');b.drop_column('service_meeting_spot_id')
    with op.batch_alter_table('profiles') as b:
        b.drop_constraint('fk_profile_preferred_spot',type_='foreignkey');b.drop_column('preferred_meeting_spot_id')
    with op.batch_alter_table('meeting_spots') as b:
        for col in ['latitude','longitude','coordinate_source','safety_attributes','safety_source','safety_checked_at']: b.drop_column(col)
