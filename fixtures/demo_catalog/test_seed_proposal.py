"""Exercise only the proposed patch, in disposable migrated SQLite databases.
Run: .venv/bin/python fixtures/demo_catalog/test_seed_proposal.py
No repository patch is applied, and no configured database is contacted.
"""
from pathlib import Path
import copy
import subprocess
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from server.app import create_app
from server.db import db
from server.models import Listing, Profile
from server.seed import validate_demo_seed_target, seed_demo_data as original_seed
from fixtures.demo_catalog import validate_catalog


def run():
    with tempfile.TemporaryDirectory(prefix='catalog_seed_proposal_') as temp:
        target = Path(temp)
        (target/'server').mkdir()
        for name in ('seed.py', 'app.py'):
            (target/'server'/name).write_text((ROOT/'server'/name).read_text())
        with (ROOT/'fixtures/demo_catalog/evan_seed_integration.patch').open() as patch:
            subprocess.run(['patch', '-p1', '-d', str(target)], stdin=patch, check=True, capture_output=True)
        module = types.ModuleType('server.catalog_seed_proposal')
        module.__package__ = 'server'
        exec(compile((target/'server/seed.py').read_text(), str(target/'server/seed.py'), 'exec'), module.__dict__)
        app = create_app({'TESTING': True, 'APP_ENV': 'development', 'AUTH_MODE': 'sandbox',
            'SANDBOX_USERS': ['proposal@unc.edu'], 'SQLALCHEMY_DATABASE_URI': 'sqlite:///'+str(target/'catalog_dev.sqlite'),
            'STORAGE_BACKEND': 'local', 'UPLOAD_DIR': str(target/'uploads')})
        with app.app_context():
            from flask_migrate import upgrade
            upgrade()
            original_seed()
            old = {row.id: row.to_dict() for row in db.session.scalars(db.select(Listing))}
            user = Profile(auth_subject='sandbox:proposal-user', display_name='User-created demo test account',
                confirmed_email_domain='unc.edu', verification_source='sandbox', is_demo=True)
            db.session.add(user); db.session.flush()
            user_row = Listing(owner_id=user.id, title='User-created test lamp', category='dorm',
                description='Preserve exactly', allowed_modes=['sale'], sale_price_cents=1234)
            db.session.add(user_row); db.session.commit()
            user_before=user_row.to_dict()
            entries, owners, counts = validate_catalog.validate()
            summary=module.seed_demo_data()
            assert len(summary)==54
            assert len(db.session.scalars(db.select(Listing)).all())==45
            assert len(db.session.scalars(db.select(Profile)).all())==14
            assert all(db.session.get(Listing, key).to_dict()==value for key,value in old.items())
            assert db.session.get(Listing,user_row.id).to_dict()==user_before
            for key in owners:
                profile=db.session.get(Profile,module._catalog_id('owner',key))
                assert profile.is_demo and profile.verification_source=='sandbox' and 'demo' in profile.display_name.lower()
            assert all(db.session.get(Listing,module._catalog_id('listing',e['key'])).public_photo_path is None for e in entries)
            edited=db.session.get(Listing,module._catalog_id('listing',entries[0]['key']))
            edited.title='Demo customized title'; edited.status='withdrawn'; edited.sale_price_cents=777
            db.session.commit(); edited_before=edited.to_dict()
            assert module.seed_demo_data()==['nothing to do; demo data already present']
            assert db.session.get(Listing,edited.id).to_dict()==edited_before
            original_env=app.config['APP_ENV']; app.config['APP_ENV']='production'
            try: module.seed_demo_data()
            except ValueError as exc: assert 'APP_ENV=development' in str(exc)
            else: raise AssertionError('production guard failed')
            app.config['APP_ENV']=original_env
            # Existing stable key claimed by a non-demo profile must fail closed.
            profile=db.session.get(Profile,module._catalog_id('owner',next(iter(owners))))
            profile.is_demo=False; db.session.commit()
            try: module.seed_demo_data()
            except ValueError as exc: assert 'not labeled sandbox demo' in str(exc)
            else: raise AssertionError('non-demo profile collision accepted')
            profile.is_demo=True; db.session.commit()
            collision=db.session.get(Listing,module._catalog_id('listing',entries[-1]['key']))
            collision.owner_id=user.id; db.session.commit()
            try: module.seed_demo_data()
            except ValueError as exc: assert 'listing collision' in str(exc)
            else: raise AssertionError('user-owned listing collision accepted')
            collision.owner_id=db.session.get(Profile,module._catalog_id('owner',entries[-1]['owner_key'])).id
            db.session.commit()
            # A last-entry API validation failure must not partially insert a new catalog.
            for e in entries: db.session.delete(db.session.get(Listing,module._catalog_id('listing',e['key'])))
            for key in owners: db.session.delete(db.session.get(Profile,module._catalog_id('owner',key)))
            db.session.commit()
            validate=validate_catalog.validate
            invalid=copy.deepcopy(entries); invalid[-1]['listing']['service_duration_minutes']=0
            validate_catalog.validate=lambda: (invalid,owners,counts)
            try:
                try: module.seed_demo_data()
                except Exception as exc:
                    from server.errors import ApiError
                    assert isinstance(exc,ApiError),type(exc)
                else: raise AssertionError('invalid fixture accepted')
                db.session.rollback()
                assert len(db.session.scalars(db.select(Listing)).all())==3
                assert len(db.session.scalars(db.select(Profile)).all())==2
            finally: validate_catalog.validate=validate
            supabase={'APP_ENV':'development','SQLALCHEMY_DATABASE_URI':'postgresql+psycopg://postgres.project:unused@aws-0-us-east-1.pooler.supabase.com:5432/postgres','SUPABASE_URL':'https://project.supabase.co'}
            try: validate_demo_seed_target(supabase)
            except ValueError: pass
            else: raise AssertionError('opt-in bypass')
            validate_demo_seed_target(supabase,allow_supabase_postgres_dev=True)
            bad=dict(supabase,SUPABASE_URL='https://another.supabase.co')
            try: validate_demo_seed_target(bad,allow_supabase_postgres_dev=True)
            except ValueError: pass
            else: raise AssertionError('wrong project accepted')
            print('PASS: proposed patch applies; migrations; 42 listings/12 owners; repeat idempotency; old demo/user preservation; customized catalog preservation; demo profile enforcement; no photos; production and Supabase opt-in guards; profile/listing collision rejection; invalid fixture zero partial inserts.')

if __name__=='__main__': run()
