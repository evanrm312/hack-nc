from datetime import timedelta
from server.db import db, utcnow
from server.models import Notification, ExchangeLocation, MeetingSpot, Listing
from tests.conftest import auth, create_listing
from tests.test_services import exchange_with_offer, WINDOW


def notices(client,headers):
    return client.get('/api/notifications',headers=headers).get_json()


def test_notification_ownership_persistence_and_retries(app,client,alice,bob):
    listing,exchange,offer=exchange_with_offer(client,alice,bob)
    base='/api/exchanges/'+exchange['id']
    assert notices(client,alice)['unread_count']==1  # requester started it
    assert notices(client,bob)['unread_count']==1  # owner proposed an offer
    response=client.post(base+'/messages',headers=alice,json={'body':'Private body must never appear in alerts'})
    assert response.status_code==201
    assert 'Private body' not in client.get('/api/notifications',headers=bob).get_data(as_text=True)
    client.post(base+'/accept',headers=alice,json={'version':offer['version']})
    count=notices(client,bob)['unread_count']
    client.post(base+'/accept',headers=alice,json={'version':offer['version']})
    assert notices(client,bob)['unread_count']==count
    note=notices(client,bob)['notifications'][0]
    assert client.post('/api/notifications/'+note['id']+'/read',headers=alice).status_code==404
    assert client.post('/api/notifications/'+note['id']+'/read',headers=bob).status_code==200
    assert notices(client,bob)['unread_count']==count-1
    assert client.get('/api/notifications').status_code==401
    assert client.get('/api/notifications',headers=bob).headers['Cache-Control']=='private, no-store'
    with app.app_context():
        db.session.remove()
        assert db.session.query(Notification).filter_by(recipient_id=note.get('recipient_id','missing')).count()==0
        assert db.session.get(Notification,note['id']).read_at is not None
    client.post('/api/notifications/read-all',headers=bob)
    assert notices(client,bob)['unread_count']==0


def test_failed_transition_does_not_notify(client,alice,bob):
    _,exchange,_=exchange_with_offer(client,alice,bob)
    before=notices(client,alice)['unread_count']
    response=client.post('/api/exchanges/'+exchange['id']+'/accept',headers=bob,json={'version':99})
    assert response.status_code==409
    assert notices(client,alice)['unread_count']==before


def test_private_locations_and_profile_preference(app,client,alice,bob):
    listing,exchange,offer=exchange_with_offer(client,alice,bob)
    with app.app_context():
        spot=MeetingSpot(label='Rams Head Plaza',public_area='South campus');db.session.add(spot);db.session.commit();spot_id=spot.id
    assert client.patch('/api/me',headers=alice,json={'preferred_meeting_spot_id':spot_id}).status_code==200
    assert client.patch('/api/me',headers=bob,json={'preferred_meeting_spot_id':'missing'}).status_code==400
    assert 'preferred_meeting_spot_id' not in client.get('/api/listings/'+listing['id']).get_json()['listing']['owner']
    base='/api/exchanges/'+exchange['id']+'/locations'
    app.config['SANDBOX_USERS'].append('third@unc.edu');third=auth('third@unc.edu')
    assert client.get(base,headers=third).status_code==403
    assert client.put(base+'/me',headers=third,json={'landmark':'Private'}).status_code==403
    assert client.put(base+'/me',headers=alice,json={'participant_id':'someone','landmark':'X'}).status_code==400
    for headers,landmark,lat in [(alice,'My area',35.9101234),(bob,'Other area',35.9071234)]:
        assert client.put(base+'/me',headers=headers,json={'landmark':landmark,'latitude':lat,'longitude':-79.0481234}).status_code==200
    result=client.get(base,headers=alice).get_json()
    assert len(result['locations'])==2 and result['ranking']=='straight_line_estimate'
    assert result['meeting_spots'][0]['preferred_by_participant'] is True
    assert result['meeting_spots'][0]['safety_attributes']['cameras'] is None
    assert result['locations'][0]['latitude'] in (35.9101,35.9071)
    with app.app_context():
        row=db.session.query(ExchangeLocation).first();row.expires_at=utcnow()-timedelta(seconds=1);db.session.commit()
    assert len(client.get(base,headers=alice).get_json()['locations'])==1
    client.post('/api/exchanges/'+exchange['id']+'/cancel',headers=alice,json={'reason':'Cannot attend'})
    with app.app_context(): assert db.session.query(ExchangeLocation).count()==0


def test_in_person_service_requires_agreed_catalog_spot(client,alice,bob,app):
    _,exchange,offer=exchange_with_offer(client,alice,bob)
    base='/api/exchanges/'+exchange['id']
    body={'service_price_cents':2500,'service_duration_minutes':60,'service_scheduled_at':WINDOW['start'],'service_delivery':'in_person'}
    assert client.post(base+'/offers',headers=alice,json=body).status_code==400
    with app.app_context():
        spot=MeetingSpot(label='Test campus spot',public_area='Public area');db.session.add(spot);db.session.commit();spot_id=spot.id
    client.post(base+'/accept',headers=bob,json={'version':offer['version']})
    body['service_meeting_spot_id']=spot_id
    row=client.post(base+'/offers',headers=alice,json=body).get_json()['offer']
    assert row['owner_accepted_at'] is None and row['requester_accepted_at'] is None
    assert client.post(base+'/accept',headers=bob,json={'version':offer['version']}).status_code==409
    first=client.post(base+'/accept',headers=alice,json={'version':row['version']})
    assert first.get_json()['exchange']['status']=='negotiating'
    second=client.post(base+'/accept',headers=bob,json={'version':row['version']})
    assert second.get_json()['exchange']['status']=='scheduled'
    assert client.post(base+'/handoff',headers=alice,json={'confirm':True}).status_code==409


def test_retried_message_and_exchange_do_not_duplicate_events(client,alice,bob,app):
    listing=create_listing(client,alice)
    key={'Idempotency-Key':'exchange-retry-key'}
    body={'listing_id':listing['id'],'mode':'sale'}
    a=client.post('/api/exchanges',headers={**bob,**key},json=body)
    b=client.post('/api/exchanges',headers={**bob,**key},json=body)
    assert a.status_code==b.status_code==201
    assert a.get_json()['exchange']['id']==b.get_json()['exchange']['id']
    base='/api/exchanges/'+a.get_json()['exchange']['id']
    before=notices(client,alice)['unread_count']
    for _ in range(2):
        r=client.post(base+'/messages',headers={**bob,'Idempotency-Key':'message-retry-key'},json={'body':'A real test message'})
        assert r.status_code==201
    assert len(client.get(base+'/messages',headers=alice).get_json()['messages'])==1
    assert notices(client,alice)['unread_count']==before+1


def test_expired_location_cleanup_command(app,client,alice,bob):
    _,exchange,_=exchange_with_offer(client,alice,bob)
    participant=client.get('/api/me',headers=alice).get_json()['profile']['id']
    with app.app_context():
        db.session.add(ExchangeLocation(exchange_id=exchange['id'],participant_id=participant,
            landmark='Temporary',expires_at=utcnow()-timedelta(hours=1)));db.session.commit()
    result=app.test_cli_runner().invoke(args=['purge-exchange-locations'])
    assert result.exit_code==0 and 'Removed 1' in result.output
    with app.app_context(): assert db.session.query(ExchangeLocation).count()==0


def test_service_offers_reject_remaining_item_fields(client,alice,bob):
    _,exchange,_=exchange_with_offer(client,alice,bob)
    base='/api/exchanges/'+exchange['id']+'/offers'
    for field,value in [('proposed_item_value_cents',100),('meeting_spot_id','x'),('meeting_spot_ids',[]),('pickup_windows',[]),('return_windows',[])]:
        response=client.post(base,headers=alice,json={'service_price_cents':2500,'service_duration_minutes':60,
            'service_scheduled_at':WINDOW['start'],field:value})
        assert response.status_code==400
        assert field in response.get_json()['error']['fields']
