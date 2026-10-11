"""Validate proposed demo fixtures; never seed the configured application database.

Run: .venv/bin/python fixtures/demo_catalog/validate_catalog.py
"""
from __future__ import annotations
import json
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
FILES = ('clothing_events', 'electronics_academics', 'dorm_outdoors', 'services')
COMMON = {'title', 'category', 'description', 'allowed_modes'}
ITEM = COMMON | {'specifications', 'condition', 'accessories', 'known_defects', 'sale_price_cents', 'rental_fee_cents', 'proposed_item_value_cents', 'collateral_percent', 'availability', 'meeting_spot_ids'}
SERVICE = COMMON | {'service_price_cents', 'service_duration_minutes', 'service_available_windows'}
MANIFEST = {'listing_key', 'desired_image_description', 'local_filename', 'source_type', 'source_url', 'license_permission_note', 'attribution_requirement'}


def check(condition, message):
    if not condition:
        raise ValueError(message)


def utc(value):
    check(isinstance(value, str) and value.endswith('Z'), f'UTC Z timestamp required: {value!r}')
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def validate():
    entries, owners, keys, titles, descriptions, filenames = [], {}, set(), set(), set(), set()
    counts = Counter()
    for name in FILES:
        doc = json.loads((Path(__file__).parent / f'{name}.json').read_text())
        check(set(doc) == {'schema_version', 'source_agent', 'owners', 'listings'}, f'{name}: envelope keys')
        check(type(doc['schema_version']) is int and doc['schema_version'] == 1, 'schema version')
        check(doc['source_agent'] in {'agent_1', 'agent_2', 'agent_3', 'agent_4'}, 'source agent')
        local_owners = set()
        for owner in doc['owners']:
            check(set(owner) == {'key', 'display_name'}, 'owner keys')
            check(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', owner['key']), 'owner stable key')
            check(owner['key'] not in owners, 'duplicate owner key')
            check('demo' in owner['display_name'].lower(), 'owner demo label')
            owners[owner['key']] = owner
            local_owners.add(owner['key'])
        for entry in doc['listings']:
            check(set(entry) == {'key', 'owner_key', 'is_demo', 'listing', 'image_manifest'}, 'entry keys')
            key, body, manifest = entry['key'], entry['listing'], entry['image_manifest']
            check(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', key) and key not in keys, 'unique stable listing key')
            keys.add(key)
            check(entry['is_demo'] is True and entry['owner_key'] in local_owners, 'demo owner reference')
            check('demo' in body['title'].lower() and 'DEMO' in body['description'], f'{key}: visible demo label')
            for field, seen in [('title', titles), ('description', descriptions)]:
                value = body[field].strip().casefold()
                check(value not in seen, f'{key}: duplicate {field}')
                seen.add(value)
            modes = body['allowed_modes']
            check(len(modes) == len(set(modes)) and modes and set(modes) <= {'sale', 'borrow', 'service'}, 'modes')
            if modes == ['service']:
                check(set(body) == SERVICE, f'{key}: service field whitelist')
                check(body['category'] in {'tutoring', 'proofreading', 'moving help'}, 'service category')
                check(type(body['service_price_cents']) is int and body['service_price_cents'] >= 0, 'service money')
                duration = body['service_duration_minutes']
                check(type(duration) is int and 1 <= duration <= 1440, 'service duration')
                check(body['service_available_windows'], 'service windows required')
                fits = False
                for window in body['service_available_windows']:
                    check(set(window) == {'start', 'end'}, 'window keys')
                    start, end = utc(window['start']), utc(window['end'])
                    check(start < end, 'window order')
                    fits |= end - start >= timedelta(minutes=duration)
                    check(start < utc('2026-10-12T04:00:00Z') and end > utc('2026-10-11T04:00:00Z'), 'Oct 11 local service availability')
                check(fits, 'no service window fits duration')
                counts['services'] += 1
            else:
                check(set(body) == ITEM, f'{key}: item field whitelist')
                check('service' not in modes, 'mixed modes')
                check(body['condition'] in {None, 'new', 'like_new', 'good', 'fair', 'worn'}, 'condition')
                check(isinstance(body['specifications'], dict) and body['specifications'].get('type'), 'searchable item type')
                check(body['meeting_spot_ids'] == [], 'no invented meeting spot IDs')
                for field in ('accessories', 'known_defects'):
                    check(isinstance(body[field], list) and all(isinstance(x, str) for x in body[field]), field)
                for field in ('sale_price_cents', 'rental_fee_cents', 'proposed_item_value_cents'):
                    value = body[field]
                    check(value is None or type(value) is int and value >= 0, field)
                check((body['sale_price_cents'] is not None) == ('sale' in modes), 'sale price/mode')
                if 'borrow' in modes:
                    check(body['proposed_item_value_cents'] is not None and body['rental_fee_cents'] is not None, 'borrow terms')
                    check(type(body['collateral_percent']) is int and 0 <= body['collateral_percent'] <= 100, 'collateral proposal')
                    counts['free_borrow'] += body['rental_fee_cents'] == 0
                else:
                    check(all(body[f] is None for f in ('rental_fee_cents', 'proposed_item_value_cents', 'collateral_percent')), 'unused loan terms must be null')
                counts['free_keep'] += 'sale' in modes and body['sale_price_cents'] == 0
                counts['both' if len(modes) == 2 else modes[0] + '_only'] += 1
                availability = body['availability']
                check(set(availability) == {'available_from', 'available_until', 'notes'}, 'availability keys')
                start, end = availability['available_from'], availability['available_until']
                if start: utc(start)
                if end: utc(end)
                if start and end: check(utc(start) < utc(end), 'item date order')
            check(set(manifest) == MANIFEST and manifest['listing_key'] == key, 'manifest shape/key')
            check(Path(manifest['local_filename']).name == manifest['local_filename'] and manifest['local_filename'] not in filenames, 'unique safe image filename')
            filenames.add(manifest['local_filename'])
            check(manifest['source_type'] == 'planned_original_photo' and manifest['source_url'] is None, 'image sourcing remains planned')
            check('pending' in manifest['license_permission_note'].lower() and 'pending' in manifest['attribution_requirement'].lower(), 'pending image permission')
            text = json.dumps(body).lower().replace('no safety rating, calibration, or mains-use claim is made', '').replace('temperature rating is unknown', '')
            check(not re.search(r'\b(?:ratings?|reviews|transactions?|verified|verification|popularity|carbon|co2|environmental impact)\b', text), f'{key}: prohibited claim')
            check(not re.search(r'\b[\w.+-]+@[\w.-]+\.[a-z]+\b|\b\d{3}[-.]\d{3}[-.]\d{4}\b', text), 'contact details')
            entries.append(entry)
    check(40 <= len(entries) <= 50, 'catalog size')
    for name, minimum in {'borrow_only': 8, 'sale_only': 8, 'both': 8, 'free_keep': 4, 'free_borrow': 4, 'services': 8}.items():
        check(counts[name] >= minimum, f'{name} below minimum')
    return entries, owners, dict(counts)


def exercise(entries):
    from server.app import create_app
    from server.db import db
    from server.models import Listing, Profile
    from server.routes.catalog import _apply_listing_fields
    from server.intelligence.matching import match_listings
    with tempfile.TemporaryDirectory(prefix='catalog_validation_') as directory:
        app = create_app({'TESTING': True, 'APP_ENV': 'development', 'AUTH_MODE': 'sandbox', 'SANDBOX_USERS': ['validator@unc.edu'], 'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + directory + '/catalog_dev.sqlite', 'STORAGE_BACKEND': 'local', 'UPLOAD_DIR': directory + '/uploads'})
        with app.app_context():
            db.create_all()
            owner = Profile(auth_subject='sandbox:catalog-validator', display_name='Demo Validator (demo account)', confirmed_email_domain='unc.edu', verification_source='sandbox', is_demo=True)
            db.session.add(owner); db.session.flush()
            rows = []
            for entry in entries:
                listing = Listing(owner_id=owner.id, status='available')
                _apply_listing_fields(listing, entry['listing'], creating=True)
                db.session.add(listing); db.session.flush()
                rows.append({**listing.to_dict(), 'id': entry['key']})
            db.session.commit()
            requests = {
                'suit': {'modes': ['borrow'], 'category': 'formalwear', 'required_specifications': {'type': 'suit', 'jacket_size': '40R'}, 'preferred_specifications': {'color': 'navy'}, 'budget_cents': 2000, 'max_deposit_cents': 8000, 'use_start': '2026-10-11T14:00:00Z', 'use_end': '2026-10-11T22:00:00Z'},
                'service': {'modes': ['service'], 'category': 'proofreading', 'required_specifications': {}, 'preferred_specifications': {}, 'budget_cents': 2000, 'service_duration_minutes': 45, 'service_time_windows': [{'start': '2026-10-11T23:00:00Z', 'end': '2026-10-12T01:00:00Z'}]},
            }
            results = {name: match_listings(request, rows) for name, request in requests.items()}
            for name, result in results.items():
                check(result['confirmed'] and result['rejected'], f'{name}: useful groups')
                check(all(e['listing_id'] in {r['id'] for r in rows} for group in ('confirmed', 'needs_confirmation', 'rejected') for e in result[group]), 'listing ID membership')
            check(results['suit']['needs_confirmation'], 'suit unknown size demonstration')
            return results


if __name__ == '__main__':
    entries, owners, counts = validate()
    results = exercise(entries)
    print(json.dumps({'total': len(entries), 'owners': len(owners), 'counts': counts, 'shared_listing_validation': len(entries), 'matching': results}, indent=2))
