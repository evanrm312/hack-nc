"""Scoped retries for exchange creation and private messages."""
from alembic import op
import sqlalchemy as sa
revision='c705exchangekeys'
down_revision='c704creationkeys'
branch_labels=depends_on=None

def upgrade():
    for table,owner in [('exchanges','requester_id'),('messages','sender_id')]:
        with op.batch_alter_table(table) as b:
            b.add_column(sa.Column('creation_key',sa.String(80)))
            b.add_column(sa.Column('creation_fingerprint',sa.String(64)))
            b.create_unique_constraint('uq_'+table+'_creation',[owner,'creation_key'])

def downgrade():
    for table in ['exchanges','messages']:
        with op.batch_alter_table(table) as b:
            b.drop_constraint('uq_'+table+'_creation',type_='unique');b.drop_column('creation_key');b.drop_column('creation_fingerprint')
