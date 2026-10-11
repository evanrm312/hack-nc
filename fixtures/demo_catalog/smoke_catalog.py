"""Seed twice and exercise real APIs in a disposable migrated development DB.

Run from the project root: .venv/bin/python fixtures/demo_catalog/smoke_catalog.py
No configured database, remote storage, or Gemini call is used. Extra calculator
listings are controlled test rows, never additions to the preserved catalog.
"""
from __future__ import annotations

import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from flask_migrate import upgrade

from server.app import create_app
from server.db import db
from server.models import Listing, MeetingSpot, PriceReference, Profile
from fixtures.demo_catalog.validate_catalog import validate

GROUPS = ('confirmed', 'needs_confirmation', 'rejected')


def run():
    entries, owners, _ = validate()
    with tempfile.TemporaryDirectory(prefix='campus_catalog_smoke_') as directory:
        app = create_app({
            'TESTING': True, 'APP_ENV': 'development', 'AUTH_MODE': 'sandbox',
            'SANDBOX_USERS': ['alice@unc.edu', 'bob@unc.edu'],
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{directory}/catalog_dev.sqlite',
            'STORAGE_BACKEND': 'local', 'UPLOAD_DIR': directory + '/uploads',
            'DISPLAY_TIMEZONE': 'America/New_York',
        })
        with app.app_context():
            upgrade()
        runner = app.test_cli_runner()
        first = runner.invoke(args=['seed-demo'])
        assert first.exit_code == 0, first.output
        with app.app_context():
            before = {
                cls.__tablename__: len(db.session.scalars(db.select(cls)).all())
                for cls in (Listing, Profile, MeetingSpot, PriceReference)
            }
            rows_before = {row.id: row.to_dict() for row in db.session.scalars(db.select(Listing))}
            files_before = set(Path(directory, 'uploads/public').rglob('*.webp'))
        second = runner.invoke(args=['seed-demo'])
        assert second.exit_code == 0, second.output
        with app.app_context():
            after = {
                cls.__tablename__: len(db.session.scalars(db.select(cls)).all())
                for cls in (Listing, Profile, MeetingSpot, PriceReference)
            }
            assert before == after
            assert rows_before == {row.id: row.to_dict() for row in db.session.scalars(db.select(Listing))}
            assert files_before == set(Path(directory, 'uploads/public').rglob('*.webp'))
            all_rows = list(db.session.scalars(db.select(Listing)))
            by_title = {row.title: row for row in all_rows}
            catalog = {entry['key']: by_title[entry['listing']['title']].to_dict() for entry in entries}
            assert len(catalog) == 54 and len({row['id'] for row in catalog.values()}) == 54
            assert all(row['owner']['is_demo'] and row['owner']['verification_source'] == 'sandbox' for row in catalog.values())
            catalog_counts = {
                'listings': len(catalog), 'owners': len(owners),
                'categories': dict(Counter(row['category'] for row in catalog.values())),
                'modes': dict(Counter('+'.join(sorted(row['allowed_modes'])) for row in catalog.values())),
                'free_to_keep': sum('sale' in row['allowed_modes'] and row['sale_price_cents'] == 0 for row in catalog.values()),
                'free_to_borrow': sum('borrow' in row['allowed_modes'] and row['rental_fee_cents'] == 0 for row in catalog.values()),
                'free_services': sum(row.get('service_price_cents') == 0 for row in catalog.values()),
                'images': sum(bool(row['public_photo_url']) for row in catalog.values()),
                'missing_images': [key for key, row in catalog.items() if not row['public_photo_url']],
            }
        client = app.test_client()
        headers = {name: {'Authorization': f'Bearer sandbox:{name}@unc.edu'} for name in ('alice', 'bob')}
        for name, key in [('alice', 'clothing-navy-suit-40r'), ('bob', 'demo-evening-essay-proofreading')]:
            me = client.get('/api/me', headers=headers[name])
            assert me.status_code == 200, me.get_json()
            assert me.get_json()['profile']['id'] == catalog[key]['owner_id']
        media_checks = 0
        for row in catalog.values():
            if row['public_photo_url']:
                media = client.get(row['public_photo_url'])
                assert media.status_code == 200 and media.mimetype == 'image/webp'
                assert media.data[:4] == b'RIFF' and media.data[8:12] == b'WEBP'
                media_checks += 1

        def create_matches(name, category, modes, budget, required=None, preferred=None, **fields):
            body = {
                'original_text': 'DEMO CONTROLLED matching smoke: ' + name,
                'normalized': {'source': 'manual', 'category': category,
                    'required_specifications': required or {}, 'preferred_specifications': preferred or {}},
                'modes': modes, 'budget_cents': budget, **fields,
            }
            actor = 'bob' if modes == ['borrow'] else 'alice'
            created = client.post('/api/requests', json=body, headers=headers[actor])
            assert created.status_code == 201, created.get_json()
            need_id = created.get_json()['request']['id']
            response = client.get(f'/api/requests/{need_id}/matches', headers=headers[actor])
            assert response.status_code == 200, response.get_json()
            result = response.get_json()
            with app.app_context():
                ids = set(db.session.scalars(db.select(Listing.id)))
            assert all(entry['listing_id'] in ids for group in GROUPS for entry in result[group])
            return result

        def entry_for(result, listing_id, group):
            return next(entry for entry in result[group] if entry['listing_id'] == listing_id)

        def summary(result, keys):
            chosen = {catalog[key]['id']: key for key in keys}
            return {
                'total_group_counts': {group: len(result[group]) for group in GROUPS},
                'every_returned_id_exists': True,
                **{group: [{field: entry[field] for field in ('listing_id', 'reasons', 'shortcomings', 'unknown_required')}
                    | {'listing_key': chosen[entry['listing_id']]}
                    for entry in result[group] if entry['listing_id'] in chosen] for group in GROUPS},
            }

        suit = create_matches('navy suit', 'formalwear', ['borrow'], 2000,
            required={'type': 'suit', 'jacket_size': '40R'}, preferred={'color': 'navy'},
            max_deposit_cents=8000, use_start='2026-10-11T14:00:00Z', use_end='2026-10-11T22:00:00Z')
        assert entry_for(suit, catalog['clothing-navy-suit-40r']['id'], 'confirmed')
        assert entry_for(suit, catalog['clothing-black-suit-size-unknown']['id'], 'needs_confirmation')
        wrong_size = entry_for(suit, catalog['clothing-charcoal-suit-44l']['id'], 'rejected')
        assert any('jacket_size' in text for text in wrong_size['shortcomings'])

        proofread = create_matches('proofreading', 'proofreading', ['service'], 2000,
            service_duration_minutes=45,
            service_time_windows=[{'start': '2026-10-11T23:00:00Z', 'end': '2026-10-12T01:00:00Z'}])
        assert entry_for(proofread, catalog['demo-evening-essay-proofreading']['id'], 'confirmed')
        expensive = entry_for(proofread, catalog['demo-extended-proofreading']['id'], 'rejected')
        assert any('budget' in text for text in expensive['shortcomings'])
        brief = entry_for(proofread, catalog['demo-late-proofreading']['id'], 'rejected')
        assert any('overlap' in text for text in brief['shortcomings'])
        assert not any('deposit' in text.lower() for group in GROUPS for entry in proofread[group]
                       for text in entry['reasons'] + entry['shortcomings'])

        # Original catalog has one $5 calculator. Preserve it, and create two
        # explicit temporary controls for the free-loan/model-rejection cases.
        calculator_body = next(entry['listing'] for entry in entries if entry['key'] == 'demo-electronics-graphing-calculator')
        for key, model, fee in [('controlled-calculator-wrong-model', 'GC-83 controlled model', 500),
                                ('controlled-calculator-free-loan', 'GC-84 demo model', 0)]:
            body = {**calculator_body, 'title': key + ' (DEMO CONTROLLED test only)',
                'description': 'DEMO CONTROLLED temporary test row; not part of the 54-listing catalog.',
                'specifications': {**calculator_body['specifications'], 'model': model}, 'rental_fee_cents': fee}
            created = client.post('/api/listings', json=body, headers=headers['alice'])
            assert created.status_code == 201, created.get_json()
            catalog[key] = created.get_json()['listing']
        calculator = create_matches('calculator', 'academic supplies', ['borrow'], 1000,
            required={'type': 'graphing calculator', 'model': 'GC-84 demo model'}, max_deposit_cents=9000,
            use_start='2026-10-11T14:00:00Z', use_end='2026-10-11T22:00:00Z')
        assert entry_for(calculator, catalog['demo-electronics-graphing-calculator']['id'], 'confirmed')
        free = entry_for(calculator, catalog['controlled-calculator-free-loan']['id'], 'confirmed')
        assert any('8500' in text for text in free['reasons']), free
        assert calculator['confirmed'][0]['listing_id'] == catalog['controlled-calculator-free-loan']['id']
        assert entry_for(calculator, catalog['controlled-calculator-wrong-model']['id'], 'rejected')

        mending = create_matches('mending', 'repair and mending', ['service'], 2000,
            service_duration_minutes=45,
            service_time_windows=[{'start': '2026-10-11T14:00:00Z', 'end': '2026-10-11T16:00:00Z'}])
        assert entry_for(mending, catalog['demo-basic-mending']['id'], 'confirmed')
        assert entry_for(mending, catalog['demo-evening-essay-proofreading']['id'], 'rejected')
        uncertain = create_matches('mending unknown schedule', 'repair and mending', ['service'], 2000,
            service_duration_minutes=45)
        assert entry_for(uncertain, catalog['demo-basic-mending']['id'], 'needs_confirmation')
        conflict = create_matches('mending schedule conflict', 'repair and mending', ['service'], 2000,
            service_duration_minutes=45,
            service_time_windows=[{'start': '2026-10-11T23:00:00Z', 'end': '2026-10-12T01:00:00Z'}])
        assert entry_for(conflict, catalog['demo-basic-mending']['id'], 'rejected')
        return {
            'database': 'disposable migrated local SQLite; removed after test',
            'gemini_calls': 0, 'normalization': 'editable manual controlled inputs',
            'first_run_created': before, 'second_run_added': {key: after[key] - before[key] for key in before},
            'duplicate_catalog_ids': 54 - len({row['id'] for key, row in catalog.items() if not key.startswith('controlled-')}),
            'second_run_added_image_files': 0,
            'legacy_listings_preserved': before['listings'] - 54,
            'catalog': catalog_counts, 'public_media_checks': media_checks,
            'showcase_authentication': {'alice': 'clothing-owner-1', 'bob': 'services-owner-1'},
            'matching': {
                'suit': summary(suit, ['clothing-navy-suit-40r', 'clothing-black-suit-size-unknown', 'clothing-charcoal-suit-44l']),
                'proofreading': summary(proofread, ['demo-evening-essay-proofreading', 'demo-extended-proofreading', 'demo-late-proofreading']),
                'calculator': summary(calculator, ['demo-electronics-graphing-calculator', 'controlled-calculator-wrong-model', 'controlled-calculator-free-loan']),
                'mending': summary(mending, ['demo-basic-mending', 'demo-button-seam-mending',
                    'demo-small-item-repair-assessment', 'demo-evening-essay-proofreading']),
                'mending_unknown_schedule': summary(uncertain, ['demo-basic-mending', 'demo-button-seam-mending']),
                'mending_schedule_conflict': summary(conflict, ['demo-basic-mending', 'demo-button-seam-mending']),
            },
        }


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
