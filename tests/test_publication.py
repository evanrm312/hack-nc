from io import BytesIO
from datetime import timedelta
from PIL import Image
import pytest
from server.db import db, utcnow
from server.models import Listing
from tests.conftest import LISTING_BODY, create_listing, publish_listing


def test_draft_cannot_be_browsed_matched_or_published_without_image(client, alice, bob):
    draft = client.post('/api/listings', headers=alice, json=LISTING_BODY).get_json()['listing']
    url = '/api/listings/' + draft['id']
    assert draft['status'] == 'draft'
    assert client.get(url).status_code == 404
    assert client.get(url, headers=bob).status_code == 404
    assert client.get(url, headers=alice).status_code == 200
    assert client.get('/api/listings?status=all').get_json()['listings'] == []
    for status in ['available', 'withdrawn']:
        response = client.patch(url, headers=alice, json={'status': status})
        if status == 'available': assert response.status_code == 400
    assert client.patch(url, headers=alice, json={'status':'available'}).status_code == 400


def test_failed_upload_and_idempotent_publication(client, alice, app):
    draft = client.post('/api/listings', headers=alice, json=LISTING_BODY).get_json()['listing']
    url = '/api/listings/' + draft['id'] + '/publish'
    for data in [{}, {'photo':(BytesIO(b'\x89PNG\r\n\x1a\ninvalid'), 'bad.png')},
                 {'photo':(BytesIO(b'x' * (64*1024+1)), 'big.png')}]:
        assert client.post(url, headers=alice, data=data).status_code in (400,413)
        assert client.get('/api/listings').get_json()['listings'] == []
    published = publish_listing(client, alice, draft)
    assert client.post(url, headers=alice).get_json()['listing']['id'] == draft['id']
    assert client.get(published['public_photo_url']).status_code == 200
    with app.app_context(): assert db.session.query(Listing).count() == 1


@pytest.mark.parametrize('status', ['reserved','sold'])
def test_photo_replacement_respects_transaction_lock(client, alice, app, status):
    listing = create_listing(client, alice)
    with app.app_context():
        db.session.get(Listing, listing['id']).status = status
        db.session.commit()
    assert client.post('/api/listings/'+listing['id']+'/photo', headers=alice,
        data={'photo':(BytesIO(b'invalid'), 'x.png')}).status_code == 409
    assert client.get('/api/listings/'+listing['id']).get_json()['listing']['public_photo_url'] == listing['public_photo_url']


def test_mode_is_filtered_before_catalog_limit(client, alice, app):
    target = create_listing(client, alice, allowed_modes=['borrow'])
    with app.app_context():
        owner = db.session.get(Listing, target['id']).owner_id
        db.session.add_all([Listing(owner_id=owner,title=f'Other {i}',category='books',allowed_modes=['sale'],
            sale_price_cents=100,created_at=utcnow()+timedelta(seconds=i+1)) for i in range(201)])
        db.session.commit()
    assert [x['id'] for x in client.get('/api/listings?mode=borrow').get_json()['listings']] == [target['id']]


def test_creation_retry_keys_are_scoped_and_reject_changed_submissions(client,alice,bob,app):
    key={'Idempotency-Key':'listing-retry-key'}
    first=client.post('/api/listings',headers={**alice,**key},json=LISTING_BODY).get_json()['listing']
    second=client.post('/api/listings',headers={**alice,**key},json=LISTING_BODY).get_json()['listing']
    assert first['id']==second['id']
    assert client.post('/api/listings',headers={**alice,**key},json={**LISTING_BODY,'title':'Different'}).status_code==409
    other=client.post('/api/listings',headers={**bob,**key},json=LISTING_BODY).get_json()['listing']
    assert other['id']!=first['id']
    body={'original_text':'Synthetic request','modes':['sale'],'normalized':{'category':'formalwear'}}
    a=client.post('/api/requests',headers={**alice,**key},json=body).get_json()['request']
    b=client.post('/api/requests',headers={**alice,**key},json=body).get_json()['request']
    assert a['id']==b['id']


def test_failed_commit_removes_new_orphan_photo(client,alice,app,monkeypatch):
    from pathlib import Path
    draft=client.post('/api/listings',headers=alice,json=LISTING_BODY).get_json()['listing']
    photo=BytesIO();Image.new('RGB',(3,3)).save(photo,format='PNG');photo.seek(0)
    def fail(): raise RuntimeError('isolated commit failure')
    with app.app_context():monkeypatch.setattr(db.session,'commit',fail)
    response=client.post('/api/listings/'+draft['id']+'/publish',headers=alice,data={'photo':(photo,'x.png')})
    assert response.status_code==500
    assert not list((Path(app.config['UPLOAD_DIR'])/'public').glob('*/*'))
    assert client.get('/api/listings').get_json()['listings']==[]


def test_matching_mode_filter_precedes_limit(client,alice,bob,app,monkeypatch):
    target=create_listing(client,bob,allowed_modes=['borrow'])
    with app.app_context():
        owner=db.session.get(Listing,target['id']).owner_id
        db.session.add_all([Listing(owner_id=owner,title=f'Sale only {i}',category='formalwear',allowed_modes=['sale'],
            sale_price_cents=100,created_at=utcnow()+timedelta(seconds=i+1)) for i in range(201)])
        db.session.commit()
    need=client.post('/api/requests',headers=alice,json={'original_text':'Borrow a navy suit','modes':['borrow'],
        'normalized':{'category':'formalwear','required_specifications':{'jacket_size':'40R'}}}).get_json()['request']
    from server.intelligence.matching import match_listings
    monkeypatch.setattr('server.routes.requests.match_listings',match_listings)
    result=client.get('/api/requests/'+need['id']+'/matches',headers=alice).get_json()
    assert target['id'] in [e['listing_id'] for k in ['confirmed','needs_confirmation'] for e in result[k]]


def test_withdrawn_status_cannot_expose_an_incomplete_draft(client,alice):
    draft=client.post('/api/listings',headers=alice,json=LISTING_BODY).get_json()['listing']
    url='/api/listings/'+draft['id']
    assert client.patch(url,headers=alice,json={'status':'withdrawn'}).status_code==400
    assert client.get(url).status_code==404
    assert client.get('/api/listings?status=all').get_json()['listings']==[]
    assert client.post(url+'/photo',headers=alice,data={'photo':(BytesIO(b'bad'),'x.png')}).status_code==409
