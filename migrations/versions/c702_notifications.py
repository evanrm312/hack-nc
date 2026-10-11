"""Private notification persistence."""
from alembic import op
import sqlalchemy as sa
revision = 'c702notifications'
down_revision = 'c701publication'
branch_labels = depends_on = None

def upgrade():
    op.create_table('notifications',sa.Column('id',sa.String(32),primary_key=True),
        sa.Column('recipient_id',sa.String(32),sa.ForeignKey('profiles.id'),nullable=False),
        sa.Column('exchange_id',sa.String(32),sa.ForeignKey('exchanges.id'),nullable=False),
        sa.Column('event_key',sa.String(200),nullable=False),sa.Column('kind',sa.String(40),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('read_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('recipient_id','event_key',name='uq_notification_event'))
    op.create_index('ix_notifications_recipient_id','notifications',['recipient_id'])
    op.create_index('ix_notifications_exchange_id','notifications',['exchange_id'])

def downgrade():
    op.drop_table('notifications')
