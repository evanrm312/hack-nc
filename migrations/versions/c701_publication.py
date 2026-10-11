"""Require photo publication for newly created drafts; preserve legacy inventory."""
from alembic import op
import sqlalchemy as sa
revision = 'c701publication'
down_revision = 'b6c28d1f9a04'
branch_labels = depends_on = None

def upgrade():
    with op.batch_alter_table('listings') as batch:
        batch.add_column(sa.Column('publication_required', sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    with op.batch_alter_table('listings') as batch:
        batch.drop_column('publication_required')
