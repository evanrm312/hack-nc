"""Bounded discovery, unread notifications, cleanup and shared request quotas."""
from alembic import op
import sqlalchemy as sa
revision='c706runtime'
down_revision='c705exchangekeys'
branch_labels=depends_on=None
INDEXES=[('ix_listing_discovery','listings',['status','created_at','id']),
         ('ix_request_discovery','need_requests',['requester_id','status','updated_at']),
         ('ix_exchange_history','exchanges',['requester_id','status','updated_at']),
         ('ix_notification_inbox','notifications',['recipient_id','read_at','created_at']),
         ('ix_location_expiry','exchange_locations',['expires_at'])]
def upgrade():
    for name,table,columns in INDEXES: op.create_index(name,table,columns)
    op.create_table('rate_limits',sa.Column('key',sa.String(64),primary_key=True),
        sa.Column('window',sa.Integer(),primary_key=True),sa.Column('count',sa.Integer(),nullable=False))
    op.create_index('ix_rate_limits_window','rate_limits',['window'])
def downgrade():
    op.drop_table('rate_limits')
    for name,table,columns in reversed(INDEXES):op.drop_index(name,table_name=table)
