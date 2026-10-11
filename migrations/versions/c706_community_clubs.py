"""Club audiences, administrative approval, and community profiles."""
from alembic import op
import sqlalchemy as sa
revision = 'c706community'
down_revision = 'c705exchangekeys'
branch_labels = depends_on = None


def upgrade():
    op.create_table('clubs', sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('slug', sa.String(80), nullable=False, unique=True),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('code_hash', sa.String(255), nullable=False),
        sa.Column('is_demo', sa.Boolean(), nullable=False))
    op.create_table('club_memberships', sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('club_id', sa.String(32), sa.ForeignKey('clubs.id'), nullable=False),
        sa.Column('profile_id', sa.String(32), sa.ForeignKey('profiles.id'), nullable=False),
        sa.Column('role', sa.String(16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('club_id','profile_id', name='uq_club_membership'),
        sa.CheckConstraint("role IN ('member','manager')", name='ck_club_member_role'))
    for column in ['club_id','profile_id']:
        op.create_index('ix_club_memberships_'+column,'club_memberships',[column])
    with op.batch_alter_table('profiles') as b:
        b.add_column(sa.Column('avatar_path',sa.String(255)))
        b.add_column(sa.Column('bio',sa.String(300)))
        b.add_column(sa.Column('graduation_year',sa.Integer()))
        b.add_column(sa.Column('show_transaction_history',sa.Boolean(),nullable=False,server_default=sa.false()))
        b.create_check_constraint('ck_profile_graduation_year','graduation_year IS NULL OR graduation_year BETWEEN 1900 AND 2200')
    with op.batch_alter_table('listings') as b:
        b.add_column(sa.Column('audience',sa.String(16),nullable=False,server_default='public'))
        b.add_column(sa.Column('club_id',sa.String(32)))
        b.create_foreign_key('fk_listing_club','clubs',['club_id'],['id'])
        b.create_index('ix_listings_club_id',['club_id'])
        b.create_check_constraint('ck_listing_club_audience',"(audience = 'public' AND club_id IS NULL) OR (audience = 'club' AND club_id IS NOT NULL)")
    with op.batch_alter_table('exchanges') as b:
        b.add_column(sa.Column('club_id',sa.String(32)))
        b.add_column(sa.Column('club_review_state',sa.String(24),nullable=False,server_default='not_required'))
        b.add_column(sa.Column('club_review_note',sa.String(300)))
        b.add_column(sa.Column('club_reviewed_by',sa.String(32)))
        b.add_column(sa.Column('club_reviewed_at',sa.DateTime(timezone=True)))
        b.add_column(sa.Column('club_review_version',sa.Integer()))
        b.create_foreign_key('fk_exchange_club','clubs',['club_id'],['id'])
        b.create_foreign_key('fk_exchange_club_reviewer','profiles',['club_reviewed_by'],['id'])
        b.create_index('ix_exchanges_club_id',['club_id'])
        b.create_check_constraint('ck_exchange_club_review',"club_review_state IN ('not_required','awaiting_participants','pending','approved','changes_requested')")
        b.create_check_constraint('ck_exchange_club_consistency',"(club_id IS NULL AND club_review_state = 'not_required') OR (club_id IS NOT NULL AND club_review_state != 'not_required')")


def downgrade():
    with op.batch_alter_table('exchanges') as b:
        b.drop_constraint('ck_exchange_club_consistency',type_='check')
        b.drop_constraint('ck_exchange_club_review',type_='check')
        b.drop_constraint('fk_exchange_club',type_='foreignkey')
        b.drop_constraint('fk_exchange_club_reviewer',type_='foreignkey')
        b.drop_index('ix_exchanges_club_id')
        for name in ['club_review_version','club_reviewed_at','club_reviewed_by','club_review_note','club_review_state','club_id']: b.drop_column(name)
    with op.batch_alter_table('listings') as b:
        b.drop_constraint('ck_listing_club_audience',type_='check')
        b.drop_constraint('fk_listing_club',type_='foreignkey');b.drop_index('ix_listings_club_id')
        b.drop_column('club_id');b.drop_column('audience')
    with op.batch_alter_table('profiles') as b:
        b.drop_constraint('ck_profile_graduation_year',type_='check')
        for name in ['show_transaction_history','graduation_year','bio','avatar_path']: b.drop_column(name)
    op.drop_table('club_memberships');op.drop_table('clubs')
