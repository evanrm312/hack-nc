"""Application tables are accessible through Flask, never browser database roles.

Supabase's postgres/service_role bypass RLS. Fail before changing permissions
when the migration caller cannot preserve this server access path. No records,
Storage objects or Storage policies are changed. Unknown future tables must be
reviewed by their owner rather than changed implicitly.
"""
from alembic import op
import sqlalchemy as sa
revision='c707browserroles'
down_revision='c706runtime'
branch_labels=depends_on=None
TABLES=('alembic_version','profiles','listings','need_requests','exchanges',
        'offer_revisions','messages','evidence','reviews','meeting_spots',
        'price_references','notifications','exchange_locations','rate_limits')
def upgrade():
    conn=op.get_bind()
    if conn.dialect.name!='postgresql':return
    roles=conn.execute(sa.text("SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated')")).scalars().all()
    if not roles:return  # ordinary isolated PostgreSQL has no browser roles
    bypass=conn.execute(sa.text('SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname=current_user')).scalar()
    if not bypass:raise RuntimeError('Server migration role must bypass RLS; review its access before applying')
    schema=conn.execute(sa.text('SELECT current_schema()')).scalar()
    quoted_schema=conn.dialect.identifier_preparer.quote_schema(schema)
    for table in TABLES:
        for role in roles:conn.execute(sa.text(f'REVOKE ALL PRIVILEGES ON TABLE {quoted_schema}."{table}" FROM "{role}"'))
        conn.execute(sa.text(f'ALTER TABLE {quoted_schema}."{table}" ENABLE ROW LEVEL SECURITY'))
        # PUBLIC is inherited by all roles and must not reintroduce a bypass.
        conn.execute(sa.text(f'REVOKE ALL PRIVILEGES ON TABLE {quoted_schema}."{table}" FROM PUBLIC'))
    for role in roles:
        conn.execute(sa.text(f'ALTER DEFAULT PRIVILEGES IN SCHEMA {quoted_schema} REVOKE ALL ON TABLES FROM "{role}"'))
    conn.execute(sa.text(f'ALTER DEFAULT PRIVILEGES IN SCHEMA {quoted_schema} REVOKE ALL ON TABLES FROM PUBLIC'))
def downgrade():
    # Never restore unsafe browser grants as an automatic rollback.
    pass
