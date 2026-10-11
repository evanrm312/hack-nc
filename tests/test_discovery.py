from datetime import timedelta
from server.db import db, utcnow
from server.models import Listing, NeedRequest, Exchange
from tests.conftest import create_listing

def recs(client,headers=None):
    response=client.get('/api/recommendations',headers=headers or {})
    assert response.status_code==200
    assert response.headers['Cache-Control']=='private, no-store'
    return response.get_json()

def test_eligibility_before_ranking(client,alice,bob,app):
    owner=client.get('/api/me',headers=alice).json['profile']['id']
    other=client.get('/api/me',headers=bob).json['profile']['id']
    own=create_listing(client,alice)
    visible=create_listing(client,bob)
    with app.app_context():
        for i in range(205):
            db.session.add(Listing(owner_id=other,title=f'Hidden {i}',category='formalwear',allowed_modes=['sale'],status='draft',sale_price_cents=100))
        for status in ['sold','withdrawn','reserved']:
            db.session.add(Listing(owner_id=other,title=status,category='formalwear',allowed_modes=['sale'],status=status,sale_price_cents=100))
        db.session.add(Listing(owner_id=other,title='Incomplete',category='formalwear',allowed_modes=['sale'],status='available',publication_required=True))
        db.session.commit()
    ids=[x['listing']['id'] for x in recs(client,alice)['items']]
    assert ids==[visible['id']]
    assert own['id'] not in ids
    assert len(recs(client)['items'])==2

def test_cold_start_determinism_diversity_and_recency(client,alice,bob,app):
    rows=[create_listing(client,bob,title=f'Item {i}',category='electronics' if i==3 else 'formalwear') for i in range(4)]
    with app.app_context():
        for i,row in enumerate(rows):db.session.get(Listing,row['id']).created_at=utcnow()-timedelta(days=i)
        db.session.commit()
    first=recs(client,alice);second=recs(client,alice)
    assert first==second and first['personalized'] is False
    assert first['items'][0]['listing']['id']==rows[0]['id']
    assert first['items'][1]['listing']['id']==rows[3]['id']
    assert all(x['reason']=='Recently listed' for x in first['items'])

def test_private_requests_modes_and_constraints(client,alice,bob,app):
    me=client.get('/api/me',headers=alice).json['profile']['id']
    other=client.get('/api/me',headers=bob).json['profile']['id']
    buy=create_listing(client,bob,allowed_modes=['sale'])
    borrow=create_listing(client,bob,allowed_modes=['borrow'],sale_price_cents=None)
    overpriced=create_listing(client,bob,title='Too expensive',allowed_modes=['borrow'],sale_price_cents=None,rental_fee_cents=99999)
    with app.app_context():
        db.session.add(NeedRequest(requester_id=me,original_text='PRIVATE SIGNAL',normalized={'category':'formalwear'},modes=['borrow'],budget_cents=2000,max_deposit_cents=20000))
        db.session.add(NeedRequest(requester_id=other,original_text='OTHER PRIVATE SIGNAL',normalized={'category':'electronics'},modes=['sale']))
        db.session.commit()
    data=recs(client,alice)
    assert data['personalized']
    assert [x['listing']['id'] for x in data['items']]==[borrow['id']]
    assert data['items'][0]['mode']=='borrow'
    assert 'PRIVATE SIGNAL' not in str(data)
    assert all(x['reason']=='Recently listed' for x in recs(client,bob)['items'])
    assert recs(client)['personalized'] is False

def test_only_actual_completed_requester_history_counts(client,alice,bob,app):
    me=client.get('/api/me',headers=alice).json['profile']['id']
    other=client.get('/api/me',headers=bob).json['profile']['id']
    listing=create_listing(client,bob)
    with app.app_context():
        db.session.add(Exchange(listing_id=listing['id'],owner_id=other,requester_id=me,mode='borrow',status='completed'))
        db.session.commit()
    data=recs(client,alice)
    assert data['items'][0]['mode']=='borrow'
    assert data['items'][0]['reason']=='Related to your completed loans'
    assert recs(client)['personalized'] is False

def test_expired_availability_is_not_recommended(client,alice,bob):
    create_listing(client,bob,availability={'available_until':'2020-01-01T00:00:00Z'})
    assert recs(client,alice)['items']==[]
