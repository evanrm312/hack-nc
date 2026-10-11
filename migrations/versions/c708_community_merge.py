"""Merge community and production readiness; isolate new club tables."""
from alembic import op
import sqlalchemy as sa

revision = 'c708communitymerge'
down_revision = ('c706community', 'c707browserroles')
branch_labels = depends_on = None


def upgrade():
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql':
        return
    roles = conn.execute(sa.text("SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated')")).scalars().all()
    if not roles:
        return
    bypass = conn.execute(sa.text('SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname=current_user')).scalar()
    if not bypass:
        raise RuntimeError('Server migration role must bypass RLS; review its access before applying')
    schema = conn.execute(sa.text('SELECT current_schema()')).scalar()
    quoted = conn.dialect.identifier_preparer.quote_schema(schema)
    for table in ('clubs', 'club_memberships'):
        for role in roles:
            conn.execute(sa.text(f'REVOKE ALL PRIVILEGES ON TABLE {quoted}."{table}" FROM "{role}"'))
        conn.execute(sa.text(f'REVOKE ALL PRIVILEGES ON TABLE {quoted}."{table}" FROM PUBLIC'))
        conn.execute(sa.text(f'ALTER TABLE {quoted}."{table}" ENABLE ROW LEVEL SECURITY'))


def downgrade():
    # As in c707, never restore unsafe browser grants on rollback.
    pass
