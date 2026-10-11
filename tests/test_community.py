"""Club privacy and administrative approval over real Flask/SQLAlchemy flows."""
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import select, func
from werkzeug.security import generate_password_hash, check_password_hash

from server.db import db, utcnow
from server.models import Club, ClubMembership, Exchange, Listing, Profile, Review, OfferRevision
from tests.conftest import auth, create_listing, publish_listing
from tests.test_exchanges import ready_exchange
from tests.test_services import LISTING as SERVICE_LISTING, WINDOW

CODE = 'FICTIONAL-TEST-CODE'


@pytest.fixture
def community(app, client, alice, bob):
    app.config['SANDBOX_USERS'] += ['carol@unc.edu', 'outsider@unc.edu']
    headers = {'alice': alice, 'bob': bob, 'carol': auth('carol@unc.edu'), 'outsider': auth('outsider@unc.edu')}
    profiles = {name: client.get('/api/me', headers=h).get_json()['profile']['id'] for name, h in headers.items()}
    club = Club(slug='fictional-test', name='Fictional DEMO Test Club', code_hash=generate_password_hash(CODE), is_demo=True)
    db.session.add(club); db.session.flush()
    for name in ['alice', 'bob', 'carol']:
        db.session.add(ClubMembership(club_id=club.id, profile_id=profiles[name], role='manager' if name == 'carol' else 'member'))
    db.session.commit()
    return club.id, headers, profiles


@pytest.fixture
def spot():
    from server.models import MeetingSpot
    row = MeetingSpot(label='Public test lobby', public_area='Central campus', is_active=True)
    db.session.add(row); db.session.commit()
    return row.id


def review(client, community, exchange, decision='approve', who='carol', note=None, version=None):
    club_id, headers, _ = community
    return client.post(f"/api/clubs/{club_id}/exchanges/{exchange['id']}/review", headers=headers[who], json={
        'decision': decision, 'note': note, 'version': version or exchange['current_offer_revision']})


def pending(client, community, spot, mode='borrow', listing_id=None):
    club_id, h, _ = community
    if mode == 'service':
        response = client.post('/api/listings', headers=h['alice'], json={**SERVICE_LISTING, 'audience': 'club', 'club_id': club_id})
        listing = publish_listing(client, h['alice'], response.get_json()['listing'])
        x = client.post('/api/exchanges', headers=h['bob'], json={'listing_id': listing['id'], 'mode': 'service'}).get_json()['exchange']
        offer = client.post(f"/api/exchanges/{x['id']}/offers", headers=h['alice'], json={
            'service_price_cents': 2500, 'service_duration_minutes': 60, 'service_scheduled_at': WINDOW['start']})
        assert offer.status_code == 201, offer.get_json()
        x = offer.get_json()['exchange']
    else:
        listing_id = listing_id or create_listing(client, h['alice'], audience='club', club_id=club_id)['id']
        x = ready_exchange(client, h['alice'], h['bob'], spot, mode=mode, listing_id=listing_id)
    for name in ['alice', 'bob']:
        r = client.post(f"/api/exchanges/{x['id']}/accept", headers=h[name], json={'version': x['current_offer_revision']})
        assert r.status_code == 200, r.get_json()
        x = r.get_json()['exchange']
    return x


def test_join_generic_secret_free_and_idempotent(client, community):
    club_id, h, profiles = community
    for code in ['wrong-code', None, '', 2]:
        r = client.post('/api/clubs/join', headers=h['outsider'], json={'code': code})
        assert r.status_code == 400
        assert r.get_json()['error']['code'] == 'invalid_club_code'
        assert 'club' not in r.get_json()['error']['fields']
    for _ in range(2):
        r = client.post('/api/clubs/join', headers=h['outsider'], json={'code': CODE})
        assert r.status_code == 200
        assert r.get_json()['membership']['role'] == 'member'
        assert CODE not in r.get_data(as_text=True) and 'code_hash' not in r.get_data(as_text=True)
    assert db.session.scalar(select(func.count()).select_from(ClubMembership).where(
        ClubMembership.club_id == club_id, ClubMembership.profile_id == profiles['outsider'])) == 1
    club = db.session.get(Club, club_id)
    assert club.code_hash != CODE and check_password_hash(club.code_hash, CODE)
    assert client.get(f'/api/clubs/{club_id}').status_code == 401
    assert client.get(f'/api/clubs/{club_id}', headers=h['bob']).status_code == 200


@pytest.mark.parametrize('mode', ['sale', 'borrow', 'service'])
def test_visibility_creation_and_photo_access(client, community, mode):
    club_id, h, _ = community
    body = SERVICE_LISTING if mode == 'service' else None
    if body:
        draft = client.post('/api/listings', headers=h['alice'], json={**body, 'audience': 'club', 'club_id': club_id}).get_json()['listing']
        listing = publish_listing(client, h['alice'], draft)
    else:
        listing = create_listing(client, h['alice'], audience='club', club_id=club_id)
    for headers in [{}, h['outsider']]:
        assert listing['id'] not in {row['id'] for row in client.get('/api/listings?status=all', headers=headers).get_json()['listings']}
        assert client.get('/api/listings/' + listing['id'], headers=headers).status_code == 404
        assert client.get(listing['public_photo_url'], headers=headers).status_code == 404
        assert client.post('/api/exchanges', headers=headers or h['outsider'], json={'listing_id': listing['id'], 'mode': mode}).status_code == 404
    assert client.get('/api/listings/' + listing['id'], headers=h['bob']).status_code == 200
    assert client.get(listing['public_photo_url'], headers=h['bob']).status_code == 200
    assert listing['id'] in {row['id'] for row in client.get('/api/listings', headers=h['bob']).get_json()['listings']}
    assert client.post('/api/listings', headers=h['outsider'], json={
        'title': 'Bad audience', 'category': 'electronics', 'allowed_modes': ['sale'], 'sale_price_cents': 0,
        'audience': 'club', 'club_id': club_id}).status_code == 400
    assert client.patch('/api/listings/' + listing['id'], headers=h['alice'], json={'audience': 'public', 'club_id': None}).status_code == 400


def test_club_listing_excluded_before_matcher(client, community, monkeypatch):
    club_id, h, _ = community
    listing = create_listing(client, h['alice'], audience='club', club_id=club_id)
    seen = []
    def matcher(request, rows):
        seen.extend(rows)
        return {'source': 'deterministic', 'confirmed': [], 'needs_confirmation': [], 'rejected': []}
    monkeypatch.setattr('server.routes.requests.match_listings', matcher)
    for person, expected in [('outsider', False), ('bob', True)]:
        need = client.post('/api/requests', headers=h[person], json={'original_text': 'Need suit', 'modes': ['borrow']}).get_json()['request']
        seen.clear()
        r = client.get(f"/api/requests/{need['id']}/matches", headers=h[person])
        assert r.status_code == 200
        assert (listing['id'] in {row['id'] for row in seen}) is expected


@pytest.mark.parametrize('mode,target', [('sale', 'reserved'), ('borrow', 'reserved'), ('service', 'scheduled')])
def test_pending_and_manager_approval_correct_transition(client, community, spot, mode, target):
    x = pending(client, community, spot, mode)
    assert x['status'] == 'negotiating' and x['club_review_state'] == 'pending'
    listing = db.session.get(Listing, x['listing_id'])
    assert listing.status == 'available' and listing.active_exchange_id is None
    assert review(client, community, x, who='bob').status_code == 403
    r = review(client, community, x)
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['exchange']['status'] == target
    assert r.get_json()['exchange']['club_review_state'] == 'approved'
    assert db.session.get(Listing, listing.id).active_exchange_id == x['id']
    assert review(client, community, x).get_json() == r.get_json()


def test_manager_participant_cannot_approve(client, community, spot):
    x = pending(client, community, spot)
    club_id, h, ids = community
    row = db.session.scalar(select(ClubMembership).where(ClubMembership.club_id == club_id, ClubMembership.profile_id == ids['alice']))
    row.role = 'manager'; db.session.commit()
    assert review(client, community, x, who='alice').status_code == 403


def test_request_changes_new_offer_and_stale_review(client, community, spot):
    x = pending(client, community, spot)
    r = review(client, community, x, decision='request_changes', note='Please clarify the schedule.')
    assert r.status_code == 200
    assert r.get_json()['exchange']['status'] == 'negotiating'
    assert r.get_json()['exchange']['club_review_state'] == 'changes_requested'
    _, h, _ = community
    assert client.post(f"/api/exchanges/{x['id']}/accept", headers=h['bob'], json={'version': x['current_offer_revision']}).status_code == 409
    r = client.post(f"/api/exchanges/{x['id']}/offers", headers=h['bob'], json={'rental_fee_cents': 1400})
    assert r.status_code == 201
    new = r.get_json()
    assert new['offer']['owner_accepted_at'] is None and new['offer']['requester_accepted_at'] is None
    assert new['exchange']['club_review_state'] == 'awaiting_participants' and new['exchange']['club_review_note'] is None
    assert review(client, community, x).status_code == 409
    assert review(client, community, new['exchange']).status_code == 409


def test_service_new_offer_resets_review(client, community, spot):
    x = pending(client, community, spot, 'service')
    _, h, _ = community
    r = client.post(f"/api/exchanges/{x['id']}/offers", headers=h['alice'], json={
        'service_price_cents': 2300, 'service_duration_minutes': 60, 'service_scheduled_at': WINDOW['start']})
    assert r.status_code == 201
    assert r.get_json()['exchange']['club_review_state'] == 'awaiting_participants'
    assert r.get_json()['offer']['owner_accepted_at'] is None


def test_manager_reservation_conflict(client, community, spot):
    club_id, h, _ = community
    listing = create_listing(client, h['alice'], audience='club', club_id=club_id)
    one = pending(client, community, spot, listing_id=listing['id'])
    two = pending(client, community, spot, listing_id=listing['id'])
    assert review(client, community, one).status_code == 200
    r = review(client, community, two)
    assert r.status_code == 409 and r.get_json()['error']['code'] == 'reservation_conflict'
    loser = db.session.get(Exchange, two['id'])
    assert loser.status == 'negotiating' and loser.club_review_state == 'pending'


def test_manager_sanitized_and_participant_routes_remain_private(client, community, spot):
    x = pending(client, community, spot)
    club_id, h, _ = community
    client.post(f"/api/exchanges/{x['id']}/messages", headers=h['bob'], json={'body': 'Secret request and private chat'})
    r = client.get(f'/api/clubs/{club_id}/exchanges', headers=h['carol'])
    data = r.get_json()['exchanges'][0]
    assert set(data) == {'id', 'listing_title', 'participants', 'mode', 'status', 'club_review_state', 'club_review_note', 'offer_version', 'agreed_terms'}
    text = r.get_data(as_text=True)
    for forbidden in ['Secret request', 'auth_subject', 'pickup_meeting_spot_id', 'return_meeting_spot_id', 'condition_snapshot', 'evidence', 'source_request_id']:
        assert forbidden not in text
    for suffix in ['', '/messages', '/evidence', '/locations']:
        assert client.get('/api/exchanges/' + x['id'] + suffix, headers=h['carol']).status_code == 403
    assert client.get(f'/api/clubs/{club_id}/exchanges', headers=h['outsider']).status_code == 404


def test_memberships_required_after_join(client, community, spot):
    x = pending(client, community, spot)
    club_id, h, ids = community
    row = db.session.scalar(select(ClubMembership).where(ClubMembership.club_id == club_id, ClubMembership.profile_id == ids['bob']))
    db.session.delete(row); db.session.commit()
    assert review(client, community, x).status_code == 404
    assert client.get('/api/exchanges/' + x['id'], headers=h['bob']).status_code == 404
    assert client.get('/api/exchanges/' + x['id'] + '/locations', headers=h['alice']).status_code == 404
    assert x['id'] not in {e['id'] for e in client.get('/api/exchanges', headers=h['alice']).get_json()['exchanges']}


def test_public_exchange_retains_transition(client, community, spot):
    _, h, _ = community
    x = ready_exchange(client, h['alice'], h['bob'], spot)
    for who in ['alice', 'bob']:
        r = client.post(f"/api/exchanges/{x['id']}/accept", headers=h[who], json={'version': x['current_offer_revision']})
        assert r.status_code == 200
    assert r.get_json()['exchange']['status'] == 'reserved'
    assert r.get_json()['exchange']['club_review_state'] == 'not_required'


def test_profile_aggregates_minimal_history_privacy_and_validation(client, community):
    _, h, ids = community
    listing = create_listing(client, h['alice'])
    now = utcnow()
    for mode in ['sale', 'borrow', 'service']:
        x = Exchange(listing_id=listing['id'], owner_id=ids['alice'], requester_id=ids['bob'], mode=mode,
                     status='completed', cancellation_reason='secret', dispute_reason='secret', updated_at=now)
        db.session.add(x); db.session.flush()
        if mode == 'sale':
            db.session.add(Review(exchange_id=x.id, reviewer_id=ids['bob'], reviewee_id=ids['alice'], stars=4, structured_answers={}, comment='private review text'))
    db.session.add(Exchange(listing_id=listing['id'], owner_id=ids['alice'], requester_id=ids['bob'], mode='sale', status='cancelled'))
    db.session.commit()
    r = client.get('/api/profiles/' + ids['alice']); p = r.get_json()['profile']
    assert p['rating'] == {'average': 4.0, 'review_count': 1}
    assert p['completed_counts']['sold_lent_provided'] == 3 and p['completed_counts']['services'] == 1
    assert p['transaction_history'] is None
    for key in ['preferred_meeting_spot_id','auth_subject','cancellation_reason','dispute_reason']:
        assert key not in r.get_data(as_text=True)
    assert client.patch('/api/me', headers=h['alice'], json={'bio': 'a' * 301}).status_code == 400
    assert client.patch('/api/me', headers=h['alice'], json={'graduation_year': True}).status_code == 400
    assert client.patch('/api/me', headers=h['alice'], json={'show_transaction_history': 'true'}).status_code == 400
    assert client.patch('/api/me', headers=h['alice'], json={'show_transaction_history': True, 'bio': 'Demo bio', 'graduation_year': 2028}).status_code == 200
    p = client.get('/api/profiles/' + ids['alice']).get_json()['profile']
    assert len(p['transaction_history']) == 3
    assert all(set(row) == {'listing_title','mode','role','completed_at'} for row in p['transaction_history'])
    assert all('secret' not in str(value) for value in p.values())
    assert client.get('/api/profiles/missing').status_code == 404


def image_bytes(size=(5, 5)):
    data = BytesIO(); Image.new('RGB', size, 'blue').save(data, format='PNG'); data.seek(0)
    return data


def test_avatar_validation_replacement_cleanup(client, alice, app):
    client.get('/api/me', headers=alice)
    assert client.post('/api/me/avatar').status_code == 401
    assert client.post('/api/me/avatar', headers=alice).status_code == 400
    for data, status in [(b'not image', 400), (b'\x89PNG\r\n\x1a\ntruncated',400), (b'a' * 65537,413)]:
        r = client.post('/api/me/avatar', headers=alice, data={'photo': (BytesIO(data), 'bad.png')})
        assert r.status_code == status
    assert client.post('/api/me/avatar', headers=alice, data={'photo': (image_bytes((4001,4001)), 'huge.png')}).status_code == 400
    first = client.post('/api/me/avatar', headers=alice, data={'photo': (image_bytes(), 'photo.png')})
    assert first.status_code == 200
    old = first.get_json()['profile']['avatar_url']
    assert client.get(old).status_code == 200
    second = client.post('/api/me/avatar', headers=alice, data={'photo': (image_bytes(), 'photo.png')})
    assert second.status_code == 200
    assert second.get_json()['profile']['avatar_url'] != old
    assert client.get(old).status_code == 404


def test_avatar_commit_failure_keeps_previous(client, alice, monkeypatch):
    first = client.post('/api/me/avatar', headers=alice, data={'photo': (image_bytes(), 'photo.png')})
    old = first.get_json()['profile']['avatar_url']
    from server.storage import get_storage
    storage = get_storage(); deleted = []
    monkeypatch.setattr(storage, 'delete', lambda scope,path: deleted.append(path))
    monkeypatch.setattr('server.routes.profiles.get_storage', lambda: storage)
    monkeypatch.setattr(db.session, 'commit', lambda: (_ for _ in ()).throw(RuntimeError('controlled failure')))
    response = client.post('/api/me/avatar', headers=alice, data={'photo': (image_bytes(), 'photo.png')})
    assert response.status_code == 500
    assert len(deleted) == 1 and deleted[0] not in old
    assert client.get(old).status_code == 200


def test_seed_clubs_hashes_roles_idempotency_and_no_fabricated_history(tmp_path):
    from tests.test_catalog import _migrated_app
    from server.seed import seed_demo_data, sandbox_subject
    from server.community_seed import DEMO_CLUBS
    app, _ = _migrated_app(tmp_path, 'community_dev.sqlite')
    with app.app_context():
        seed_demo_data()
        hashes = {row.slug: row.code_hash for row in db.session.scalars(select(Club))}
        assert len(hashes) == 2
        before = {row.id for row in db.session.scalars(select(ClubMembership))}
        assert len(before) == 5
        seed_demo_data()
        assert before == {row.id for row in db.session.scalars(select(ClubMembership))}
        assert hashes == {row.slug: row.code_hash for row in db.session.scalars(select(Club))}
        for slug, _, code, roles in DEMO_CLUBS:
            assert check_password_hash(hashes[slug], code) and code not in hashes[slug]
            club = db.session.scalar(select(Club).where(Club.slug == slug))
            assert club.is_demo and 'DEMO' in club.name
            for email, role in roles.items():
                p = db.session.scalar(select(Profile).where(Profile.auth_subject == sandbox_subject(email)))
                assert db.session.scalar(select(ClubMembership).where(ClubMembership.club_id == club.id, ClubMembership.profile_id == p.id)).role == role
        assert db.session.scalar(select(func.count()).select_from(Exchange)) == 0
        assert db.session.scalar(select(func.count()).select_from(Review)) == 0


def test_migration_preserves_existing_data_and_defaults(tmp_path):
    from flask_migrate import upgrade, downgrade
    from server.app import create_app
    from sqlalchemy import text
    app = create_app({'TESTING': True, 'APP_ENV': 'development', 'AUTH_MODE': 'sandbox',
        'SANDBOX_USERS': ['alice@unc.edu'], 'STORAGE_BACKEND': 'local', 'UPLOAD_DIR': str(tmp_path / 'uploads'),
        'SQLALCHEMY_DATABASE_URI': f"sqlite:///{tmp_path / 'upgrade.sqlite'}"})
    with app.app_context():
        upgrade(revision='c705exchangekeys')
        db.session.execute(text("INSERT INTO profiles (id, auth_subject, display_name, confirmed_email_domain, verification_source, is_demo, created_at) VALUES ('old', 'existing', 'Keep', 'unc.edu', 'sandbox', 1, CURRENT_TIMESTAMP)"))
        db.session.commit()
        upgrade()
        p = db.session.get(Profile, 'old')
        assert p.display_name == 'Keep' and p.show_transaction_history is False and p.avatar_path is None
        db.session.remove()
        downgrade(revision='c705exchangekeys')
        assert db.session.execute(text("SELECT display_name FROM profiles WHERE id='old'")).scalar_one() == 'Keep'
        db.session.remove()
        upgrade()


def test_club_history_title_never_becomes_public(client, community):
    club_id, h, ids = community
    listing = create_listing(client, h['alice'], audience='club', club_id=club_id, title='Secret club item')
    db.session.add(Exchange(listing_id=listing['id'], owner_id=ids['alice'], requester_id=ids['bob'], mode='sale',
        status='completed', club_id=club_id, club_review_state='approved'))
    db.session.commit()
    client.patch('/api/me', headers=h['alice'], json={'show_transaction_history': True})
    response = client.get('/api/profiles/' + ids['alice'])
    assert 'Secret club item' not in response.get_data(as_text=True)
    assert response.get_json()['profile']['completed_counts']['sold_lent_provided'] == 1
    assert response.get_json()['profile']['transaction_history'] == []


def test_club_constraints_and_role_unchanged_on_repeated_manager_join(client, community):
    club_id, h, ids = community
    response = client.post('/api/clubs/join', headers=h['carol'], json={'code': CODE})
    assert response.get_json()['membership']['role'] == 'manager'
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db.session.add(ClubMembership(club_id=club_id, profile_id=ids['bob'], role='member'))
        db.session.commit()
    db.session.rollback()
    with pytest.raises(IntegrityError):
        row = db.session.scalar(select(ClubMembership).where(ClubMembership.profile_id == ids['bob']))
        row.role = 'administrator'; db.session.commit()
    db.session.rollback()
    with pytest.raises(IntegrityError):
        db.session.add(Listing(owner_id=ids['alice'], title='Invalid audience', category='electronics', allowed_modes=['sale'], audience='public', club_id=club_id))
        db.session.commit()
    db.session.rollback()


def test_service_schedule_change_blocks_manager_approval(client, community, spot):
    x = pending(client, community, spot, 'service')
    listing = db.session.get(Listing, x['listing_id'])
    listing.service_available_windows = [{'start': '2030-10-12T12:00:00Z', 'end': '2030-10-12T12:30:00Z'}]
    db.session.commit()
    r = review(client, community, x)
    assert r.status_code == 409 and r.get_json()['error']['code'] == 'schedule_unavailable'
    assert db.session.get(Exchange, x['id']).status == 'negotiating'


def test_club_private_photo_preview_and_draft_guessing(client, community):
    club_id, h, _ = community
    r = client.post('/api/listings', headers=h['alice'], json={'title': 'Draft', 'category': 'electronics', 'allowed_modes': ['sale'],
        'sale_price_cents': 0, 'audience': 'club', 'club_id': club_id, 'description': 'A demo draft'})
    draft = r.get_json()['listing']
    assert client.get('/api/listings/' + draft['id'], headers=h['bob']).status_code == 404
    listing = publish_listing(client, h['alice'], draft)
    preview = client.get(listing['public_photo_url'] + '?preview=1', headers=h['bob'])
    assert preview.status_code == 200 and preview.get_json()['data_url'].startswith('data:image/jpeg;base64,')
    assert 'no-store' in preview.headers['Cache-Control']
    assert client.get(listing['public_photo_url'] + '?preview=1').status_code == 404
