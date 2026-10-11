from flask_migrate import upgrade
from sqlalchemy import text
from server.app import create_app
from server.db import db

def test_readiness_checks_database_and_schema(app,client):
    assert client.get('/healthz').status_code==200
    assert client.get('/api/ready').status_code==503  # create_all is not a migrated DB
    with app.app_context():
        from flask_migrate import stamp
        stamp()
    assert client.get('/api/ready').status_code==200
    with app.app_context():db.session.execute(text('UPDATE alembic_version SET version_num=\'c705exchangekeys\''));db.session.commit()
    assert client.get('/api/ready').status_code==503

def test_shared_rate_limit_and_independent_quota(app,client,alice,bob):
    app.config.update(RATE_LIMIT_ENABLED=True,WRITE_RATE_PER_MINUTE=2)
    for _ in range(2):assert client.patch('/api/me',headers=alice,json={'display_name':'A'}).status_code==200
    response=client.patch('/api/me',headers=alice,json={'display_name':'A'})
    assert response.status_code==429 and int(response.headers['Retry-After'])>0
    assert client.patch('/api/me',headers=bob,json={'display_name':'B'}).status_code==200
    assert client.get('/api/me',headers=alice).status_code==200
    from server.models.rate_limit import RateLimit
    with app.app_context():
        db.session.remove()
        rows=db.session.scalars(db.select(RateLimit)).all()
        assert len(rows)==2 and max(r.count for r in rows)==2
        assert all('alice' not in r.key for r in rows)

def test_normalization_rate_blocks_provider_before_call(app,client,alice,monkeypatch):
    app.config.update(RATE_LIMIT_ENABLED=True,NORMALIZE_RATE_PER_MINUTE=1)
    import server.routes.requests as routes
    calls=[]
    monkeypatch.setattr(routes,'normalize_request',lambda *a,**k:calls.append(True) or {'source':'manual'})
    assert client.post('/api/requests/normalize',headers=alice,json={'text':'A suit'}).status_code==200
    assert client.post('/api/requests/normalize',headers=alice,json={'text':'A suit'}).status_code==429
    assert calls==[True]

def test_expired_cleanup_is_idempotent_and_preserves_live_data(app,client,alice,bob):
    from tests.test_services import exchange_with_offer
    from server.models import ExchangeLocation,MeetingSpot
    from datetime import timedelta
    from server.db import utcnow
    _,exchange,_=exchange_with_offer(client,alice,bob)
    me=client.get('/api/me',headers=alice).json['profile']['id'];other=client.get('/api/me',headers=bob).json['profile']['id']
    with app.app_context():
        db.session.add(MeetingSpot(label='Keep',public_area='Campus'))
        db.session.add_all([ExchangeLocation(exchange_id=exchange['id'],participant_id=me,expires_at=utcnow()-timedelta(hours=1)),ExchangeLocation(exchange_id=exchange['id'],participant_id=other,expires_at=utcnow()+timedelta(hours=1))]);db.session.commit()
    for expected in ['Removed 1','Removed 0']:
        result=app.test_cli_runner().invoke(args=['purge-exchange-locations'])
        assert result.exit_code==0 and expected in result.output
    with app.app_context():
        assert db.session.query(ExchangeLocation).count()==1
        assert db.session.query(MeetingSpot).count()==1


def test_production_rejects_sqlite_and_short_secrets(tmp_path):
    import pytest
    base={'APP_ENV':'production','AUTH_MODE':'supabase','SUPABASE_URL':'https://example.invalid',
          'SUPABASE_ANON_KEY':'placeholder','UPLOAD_DIR':str(tmp_path/'uploads'),
          'SECRET_KEY':'test-only-long-secret-for-production'}
    with pytest.raises(RuntimeError,match='postgresql'):
        create_app({**base,'SQLALCHEMY_DATABASE_URI':'sqlite:///:memory:'})
    with pytest.raises(RuntimeError,match='SECRET_KEY'):
        create_app({**base,'SECRET_KEY':'short'})


def test_production_errors_do_not_log_sql_or_sensitive_values(app,client,caplog):
    @app.get('/api/qa-error')
    def api_error():raise RuntimeError('private location and token must not appear')
    @app.get('/qa-error')
    def page_error():raise RuntimeError('private location and token must not appear')
    app.config['APP_ENV']='production'
    for path in ['/api/qa-error','/qa-error']:
        response=client.get(path)
        assert response.status_code==500
        assert 'private location' not in response.text
    assert 'private location' not in caplog.text
    assert 'RuntimeError' in caplog.text


def test_sqlite_override_does_not_inherit_postgres_connection_arguments(tmp_path,monkeypatch):
    from server.config import Config
    monkeypatch.setattr(Config,'SQLALCHEMY_ENGINE_OPTIONS',{'connect_args':{'connect_timeout':5}})
    app=create_app({'APP_ENV':'development','AUTH_MODE':'sandbox','SANDBOX_USERS':['a@unc.edu'],
        'SQLALCHEMY_DATABASE_URI':'sqlite:///:memory:','STORAGE_BACKEND':'local','UPLOAD_DIR':str(tmp_path/'uploads')})
    with app.app_context():
        assert app.config['SQLALCHEMY_ENGINE_OPTIONS']=={}
        assert db.session.execute(text('SELECT 1')).scalar()==1
