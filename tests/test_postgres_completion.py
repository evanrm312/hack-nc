"""Destructive checks exclusively within a disposable schema in TEST_DATABASE_URL."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from io import BytesIO
from uuid import uuid4
from threading import Barrier, Lock
import pytest
from flask_migrate import upgrade
from sqlalchemy import create_engine,text,inspect
from server.app import create_app
from server.db import db
from server.models import Listing,Notification,Exchange,MeetingSpot
from tests.conftest import auth,create_listing
from tests.test_postgres_catalog import _isolated_postgres_target

@contextmanager
def isolated(tmp_path):
    target=_isolated_postgres_target();schema='completion_'+uuid4().hex
    admin=create_engine(target)
    with admin.begin() as c:c.execute(text(f'CREATE SCHEMA "{schema}"'))
    app=create_app({'TESTING':True,'APP_ENV':'development','AUTH_MODE':'sandbox',
        'SANDBOX_USERS':['alice@unc.edu','bob@unc.edu','charlie@unc.edu'],'STORAGE_BACKEND':'local',
        'UPLOAD_DIR':str(tmp_path/'uploads'),'SQLALCHEMY_DATABASE_URI':target,
        'SQLALCHEMY_ENGINE_OPTIONS':{'connect_args':{'options':f'-csearch_path={schema}'}}})
    try:yield app
    finally:
        with app.app_context():db.session.remove();db.engine.dispose()
        with admin.begin() as c:c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()

def test_upgrade_preserves_existing_service_item_and_private_records(tmp_path):
    with isolated(tmp_path) as app,app.app_context():
        upgrade(revision='b6c28d1f9a04')
        # Reflect the deployed schema, avoiding new model columns before upgrade.
        from sqlalchemy import MetaData,Table
        from server.db import utcnow
        meta=MetaData();p=Table('profiles',meta,autoload_with=db.engine);l=Table('listings',meta,autoload_with=db.engine);req=Table('need_requests',meta,autoload_with=db.engine)
        db.session.execute(p.insert().values(id='owner',auth_subject='old-owner',display_name='Existing',confirmed_email_domain='unc.edu',verification_source='sandbox',is_demo=True,created_at=utcnow()))
        common=dict(owner_id='owner',specifications={},accessories=[],known_defects=[],availability={},meeting_spot_ids=[],status='available',created_at=utcnow(),updated_at=utcnow())
        db.session.execute(l.insert(),[dict(common,id='old-item',title='Existing item',category='formalwear',allowed_modes=['borrow'],proposed_item_value_cents=20000),dict(common,id='old-service',title='Existing service',category='tutoring',allowed_modes=['service'],proposed_item_value_cents=None)])
        db.session.execute(req.insert().values(id='old-request',requester_id='owner',original_text='Existing private request',normalized={'category':'formalwear'},modes=['borrow'],pickup_windows=[],visibility='private',status='draft',created_at=utcnow(),updated_at=utcnow()))
        schema=db.session.execute(text('SELECT current_schema()')).scalar()
        roles=db.session.execute(text("SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated')")).scalars().all()
        if roles:
            for role in roles:db.session.execute(text(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"'))
        db.session.commit()
        before=db.session.execute(l.select().order_by(l.c.id)).mappings().all();before=[dict(r) for r in before]
        db.session.remove()
        upgrade()
        for row in before:
            after=db.session.execute(text('SELECT * FROM listings WHERE id=:id'),{'id':row['id']}).mappings().one()
            assert all(after[k]==v for k,v in row.items())
            assert after['publication_required'] is False
        assert db.session.execute(text('SELECT version_num FROM alembic_version')).scalar()=='c707browserroles'
        assert {'notifications','exchange_locations','rate_limits'} <= set(inspect(db.engine).get_table_names())
        assert db.session.execute(text("SELECT original_text FROM need_requests WHERE id='old-request'")).scalar()=='Existing private request'
        for role in roles:
            assert not db.session.execute(text("SELECT has_table_privilege(:role,:table,'SELECT,INSERT,UPDATE,DELETE')"),{'role':role,'table':schema+'.notifications'}).scalar()
            assert not db.session.execute(text("SELECT has_table_privilege(:role,:table,'SELECT,INSERT,UPDATE,DELETE')"),{'role':role,'table':schema+'.messages'}).scalar()
        assert 'ix_notification_inbox' in {i['name'] for i in inspect(db.engine).get_indexes('notifications')}

def test_postgres_publication_retry_and_notification_concurrency(tmp_path):
    with isolated(tmp_path) as app:
        with app.app_context():upgrade()
        alice,bob=auth('alice@unc.edu'),auth('bob@unc.edu')
        client=app.test_client();client.get('/api/me',headers=alice);client.get('/api/me',headers=bob)
        from tests.conftest import LISTING_BODY
        draft=client.post('/api/listings',headers=alice,json=LISTING_BODY).json['listing'];barrier=Barrier(2)
        image=(__import__('pathlib').Path(__file__).resolve().parents[1]/'static/assets/leaves.webp').read_bytes()
        def publish(_):
            barrier.wait()
            response=app.test_client().post('/api/listings/'+draft['id']+'/publish',headers=alice,data={'photo':(BytesIO(image),'photo.webp')})
            return response.status_code,response.json['listing']['public_photo_url']
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(publish,range(2)))
        assert results[0]==results[1] and results[0][0]==200
        assert len(list((tmp_path/'uploads/public').rglob('*.webp')))==1
        body={'listing_id':draft['id'],'mode':'sale'};headers={**bob,'Idempotency-Key':'pg-exchange-creation'};barrier=Barrier(2)
        def create(_):
            barrier.wait();r=app.test_client().post('/api/exchanges',headers=headers,json=body);return r.status_code,r.json['exchange']['id']
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(create,range(2)))
        assert results[0]==results[1] and results[0][0]==201
        with app.app_context():
            assert db.session.query(Exchange).count()==1
            assert db.session.query(Notification).filter_by(kind='exchange_created').count()==1

def test_postgres_acceptance_reservation_and_message_deduplication(tmp_path):
    with isolated(tmp_path) as app:
        with app.app_context():
            upgrade();spot=MeetingSpot(label='Isolated campus spot',public_area='Campus');db.session.add(spot);db.session.commit();spot_id=spot.id
        alice,bob,third=auth('alice@unc.edu'),auth('bob@unc.edu'),auth('charlie@unc.edu')
        client=app.test_client()
        from tests.test_exchanges import ready_exchange,accept
        listing=create_listing(client,alice)
        first=ready_exchange(client,alice,bob,spot_id,mode='sale',listing_id=listing['id'])
        second=ready_exchange(client,alice,third,spot_id,mode='sale',listing_id=listing['id'])
        assert accept(client,first['id'],alice).status_code==200
        assert accept(client,second['id'],alice).status_code==200
        barrier=Barrier(2)
        def competing(args):
            barrier.wait();ex,header=args;return accept(app.test_client(),ex['id'],header).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(competing,[(first,bob),(second,third)]))
        assert sorted(results)==[200,409]
        with app.app_context():winner=db.session.get(Listing,listing['id']).active_exchange_id
        headers=bob if winner==first['id'] else third
        barrier=Barrier(2)
        def again(_):
            barrier.wait();return accept(app.test_client(),winner,headers).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:assert list(pool.map(again,range(2)))==[200,200]
        barrier=Barrier(2)
        def message(_):
            barrier.wait();r=app.test_client().post('/api/exchanges/'+winner+'/messages',headers={**headers,'Idempotency-Key':'pg-message-retry'},json={'body':'Private isolated message'});return r.status_code,r.json['message']['id']
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(message,range(2)))
        assert results[0]==results[1] and results[0][0]==201
        with app.app_context():assert db.session.query(Notification).filter_by(kind='message').count()==1


def test_concurrent_first_signin_creates_one_profile(tmp_path):
    from sqlalchemy import event
    from server.models import Profile
    with isolated(tmp_path) as app:
        with app.app_context():
            upgrade();engine=db.engine
        barrier=Barrier(2)
        lookup_lock=Lock();lookup_count=0
        def simultaneous_lookup(connection,cursor,statement,parameters,context,executemany):
            nonlocal lookup_count
            if statement.startswith('SELECT profiles.') and 'WHERE profiles.auth_subject =' in statement:
                with lookup_lock:
                    lookup_count+=1
                    initial_lookup=lookup_count<=2
                if initial_lookup:barrier.wait(timeout=10)
        event.listen(engine,'after_cursor_execute',simultaneous_lookup)
        try:
            def first_login(_):
                response=app.test_client().get('/api/me',headers=auth('alice@unc.edu'))
                return response.status_code,response.json.get('profile',{}).get('id')
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(first_login,range(2)))
        finally:event.remove(engine,'after_cursor_execute',simultaneous_lookup)
        assert results[0]==results[1] and results[0][0]==200
        with app.app_context():assert db.session.query(Profile).count()==1
