"""Protected catalog integration, using isolated local development targets only."""
from pathlib import Path

import pytest
from sqlalchemy import func, select

from server.db import db
from server.models import Listing, Profile
from server.seed import _catalog_id, seed_demo_data
from server.auth.identity import resolve_identity
from tests.test_catalog import _migrated_app


@pytest.fixture
def catalog_app(tmp_path):
    app, _ = _migrated_app(tmp_path, 'catalog_dev.sqlite')
    app.config['SANDBOX_USERS'] = ['alice@unc.edu', 'bob@unc.edu']
    return app


def test_catalog_seed_idempotent_preserves_rows_and_public_media(catalog_app):
    client = catalog_app.test_client()
    client.get('/api/me', headers={'Authorization': 'Bearer sandbox:alice@unc.edu'})
    with catalog_app.app_context():
        alice_subject = resolve_identity('sandbox:alice@unc.edu', catalog_app.config).subject
        alice = db.session.scalar(select(Profile).where(Profile.auth_subject == alice_subject))
        alice_id = alice.id
        unrelated = Listing(owner_id=alice.id, title='User-created lamp', description='Keep exactly',
                            category='dorm essentials', allowed_modes=['sale'], sale_price_cents=1234)
        db.session.add(unrelated); db.session.commit()
        unrelated_before = unrelated.to_dict()
        first = seed_demo_data()
        assert sum('demo catalog listing created:' in line for line in first) == 54
        assert db.session.scalar(select(func.count()).select_from(Listing)) == 60
        unrelated_after = db.session.get(Listing, unrelated.id).to_dict()
        # Seeding intentionally adds visible demo club memberships; listing
        # fields and every preexisting owner attribute must remain unchanged.
        assert len(unrelated_after["owner"]["clubs"]) == 2
        unrelated_after["owner"]["clubs"] = unrelated_before["owner"]["clubs"]
        assert unrelated_after == unrelated_before
        navy = db.session.get(Listing, _catalog_id('listing', 'clothing-navy-suit-40r'))
        assert navy.owner_id == alice_id
        bob_subject = resolve_identity('sandbox:bob@unc.edu', catalog_app.config).subject
        bob = db.session.scalar(select(Profile).where(Profile.auth_subject == bob_subject))
        assert bob and bob.is_demo and bob.verification_source == 'sandbox'
        assert all(p.is_demo and p.verification_source == 'sandbox' for p in db.session.scalars(select(Profile)))
        photos = {l.id: l.public_photo_path for l in db.session.scalars(select(Listing)) if l.public_photo_path}
        assert len(photos) == 52
        assert all('fixtures/' not in path for path in photos.values())
        assert 'illustrative licensed reference' in navy.description
        navy.sale_price_cents = 777; navy.status = 'withdrawn'
        db.session.commit(); before = navy.to_dict()
        files = sorted(Path(catalog_app.config['UPLOAD_DIR']).rglob('*.webp'))
        assert seed_demo_data() == ['nothing to do; demo data already present']
        assert db.session.get(Listing, navy.id).to_dict() == before
        assert photos == {l.id: l.public_photo_path for l in db.session.scalars(select(Listing)) if l.public_photo_path}
        assert files == sorted(Path(catalog_app.config['UPLOAD_DIR']).rglob('*.webp'))
        media_url = '/media/public/' + next(iter(photos.values()))
    response = client.get(media_url)
    assert response.status_code == 200 and response.mimetype == 'image/webp'


def test_storage_failure_keeps_catalog_and_no_fake_paths(catalog_app, monkeypatch):
    class BrokenStorage:
        def save(self, *args):
            raise RuntimeError('secret must not reach logs')
    monkeypatch.setattr('server.storage.get_storage', lambda: BrokenStorage())
    with catalog_app.app_context():
        result = seed_demo_data()
        assert sum('photo unavailable:' in line for line in result) == 52
        assert db.session.scalar(select(func.count()).select_from(Listing)) == 59
        assert not any(row.public_photo_path for row in db.session.scalars(select(Listing)))


def test_failed_commit_rolls_back_rows_and_removes_saved_images(catalog_app, monkeypatch):
    with catalog_app.app_context():
        def broken_commit():
            raise RuntimeError('controlled commit failure')
        monkeypatch.setattr(db.session, 'commit', broken_commit)
        with pytest.raises(RuntimeError, match='controlled commit failure'):
            seed_demo_data()
        assert db.session.scalar(select(func.count()).select_from(Listing)) == 0
        assert not list(Path(catalog_app.config['UPLOAD_DIR']).rglob('*.webp'))


@pytest.mark.parametrize('kind', ['profile', 'listing'])
def test_catalog_collision_fails_without_partial_inserts(catalog_app, kind):
    with catalog_app.app_context():
        owner = Profile(auth_subject='unrelated-real', display_name='Unrelated profile',
                        confirmed_email_domain='unc.edu', verification_source='supabase', is_demo=False)
        if kind == 'profile':
            owner.id = _catalog_id('owner', 'clothing-owner-1')
        db.session.add(owner); db.session.flush()
        if kind == 'listing':
            db.session.add(Listing(id=_catalog_id('listing', 'clothing-navy-suit-40r'), owner_id=owner.id,
                                  title='Unrelated listing', category='clothing', allowed_modes=['sale'], sale_price_cents=123))
        db.session.commit()
        with pytest.raises(ValueError, match='collision'):
            seed_demo_data()
        assert db.session.scalar(select(func.count()).select_from(Profile)) == 1
        assert db.session.scalar(select(func.count()).select_from(Listing)) == (kind == 'listing')


def test_direct_seed_guard_and_unsupported_showcase_identity(catalog_app):
    with catalog_app.app_context():
        catalog_app.config['APP_ENV'] = 'production'
        with pytest.raises(ValueError, match='APP_ENV=development'):
            seed_demo_data()
        assert db.session.scalar(select(func.count()).select_from(Listing)) == 0
        catalog_app.config['APP_ENV'] = 'development'
        catalog_app.config['SANDBOX_USERS'] = []
        seed_demo_data()
        from server.seed import DEMO_USERS, sandbox_subject
        sign_in_subjects = {sandbox_subject(email) for email, _ in DEMO_USERS}
        assert all(':demo-catalog:v1:' in p.auth_subject or p.auth_subject in sign_in_subjects for p in db.session.scalars(select(Profile)))


def test_old_namespaced_showcase_owner_maps_without_replacing_id(catalog_app):
    with catalog_app.app_context():
        old = Profile(id=_catalog_id('owner', 'clothing-owner-1'),
                      auth_subject='sandbox:demo-catalog:v1:clothing-owner-1',
                      display_name='Demo customized owner', confirmed_email_domain='unc.edu',
                      verification_source='sandbox', is_demo=True)
        db.session.add(old); db.session.commit()
        old_id = old.id
        seed_demo_data()
        assert db.session.get(Profile, old_id).auth_subject == resolve_identity('sandbox:alice@unc.edu', catalog_app.config).subject
        assert db.session.get(Profile, old_id).display_name == 'Demo customized owner'


@pytest.mark.parametrize('validator', ['fixtures.demo_catalog.validate_images.validate_images', 'fixtures.demo_catalog.validate_catalog.validate'])
def test_invalid_fixtures_rejected_before_storage_or_partial_inserts(catalog_app, monkeypatch, validator):
    def invalid(*args, **kwargs):
        raise ValueError('controlled invalid fixture/hash/path')
    monkeypatch.setattr(validator, invalid)
    def no_storage():
        raise AssertionError('storage must not be reached')
    monkeypatch.setattr('server.storage.get_storage', no_storage)
    with catalog_app.app_context():
        with pytest.raises(ValueError, match='controlled invalid'):
            seed_demo_data()
        assert db.session.scalar(select(func.count()).select_from(Profile)) == 0
        assert db.session.scalar(select(func.count()).select_from(Listing)) == 0


def test_old_demo_row_gets_missing_photo_and_appended_credit(catalog_app):
    with catalog_app.app_context():
        seed_demo_data()
        listing = db.session.get(Listing, _catalog_id('listing', 'clothing-navy-suit-40r'))
        listing.public_photo_path = None
        listing.description = 'DEMO customized wording retained.'
        listing.rental_fee_cents = 999; listing.status = 'withdrawn'
        db.session.commit()
        seed_demo_data()
        assert listing.description.startswith('DEMO customized wording retained.')
        assert 'illustrative licensed reference' in listing.description
        assert listing.public_photo_path
        assert listing.rental_fee_cents == 999 and listing.status == 'withdrawn'


def test_legacy_non_demo_owner_is_not_overwritten(catalog_app):
    from server.seed import DEMO_LENDER_SUBJECT
    with catalog_app.app_context():
        owner = Profile(auth_subject=DEMO_LENDER_SUBJECT, display_name='Preserve real profile',
                        confirmed_email_domain='unc.edu', verification_source='supabase', is_demo=False)
        db.session.add(owner); db.session.commit()
        with pytest.raises(ValueError, match='Legacy demo lender subject collision'):
            seed_demo_data()
        assert db.session.scalar(select(func.count()).select_from(Listing)) == 0
        assert db.session.scalar(select(func.count()).select_from(Profile)) == 1
        assert not list(Path(catalog_app.config['UPLOAD_DIR']).rglob('*.webp'))


def test_missing_local_reference_does_not_block_other_listings(catalog_app, tmp_path, monkeypatch):
    import shutil
    from fixtures.demo_catalog import validate_images
    base = tmp_path / 'isolated_fixtures'
    shutil.copytree(validate_images.BASE / 'images', base / 'images')
    shutil.copytree(validate_images.BASE / 'image_manifests', base / 'image_manifests')
    record = next(record for record in validate_images.manifests() if record.get('status') != 'missing')
    (base / record['local_filename']).unlink()
    monkeypatch.setattr(validate_images, 'BASE', base)
    with catalog_app.app_context():
        seed_demo_data()
        assert db.session.scalar(select(func.count()).select_from(Listing)) == 59
        assert db.session.get(Listing, _catalog_id('listing', record['listing_key'])).public_photo_path is None
        assert sum(bool(row.public_photo_path) for row in db.session.scalars(select(Listing))) == 51
