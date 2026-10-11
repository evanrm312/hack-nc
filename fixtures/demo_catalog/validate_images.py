"""Read-only checks for licensed demo references; no configured database access."""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime
from urllib.parse import urlparse
from collections import Counter
from pathlib import Path
from PIL import Image

BASE = Path(__file__).resolve().parent
REQUIRED = {'listing_key','listing_title','local_filename','source_type','source_page_url','original_media_url','creator','license_name','license_url','required_attribution','width','height','byte_size','sha256','visual_description','checked_by_agent','checked_at'}

def manifests():
    return [entry for path in sorted((BASE/'image_manifests').glob('*.json')) for entry in json.loads(path.read_text())]

def difference_hash(image):
    """256-bit horizontal difference hash, suitable for duplicate triage."""
    pixels = list(image.convert('L').resize((17,16)).get_flattened_data())
    result = 0
    for y in range(16):
        for x in range(16):
            result = (result << 1) | (pixels[y*17+x] > pixels[y*17+x+1])
    return result

def validate_images(entries=None, *, allow_missing_files=False):
    """Validate references; seed callers may tolerate absent files, never tampering."""
    if entries is None:
        try:
            from .validate_catalog import validate
        except ImportError:
            from validate_catalog import validate
        entries, _, _ = validate()
    catalog = {entry['key']: entry['listing']['title'] for entry in entries}
    records = manifests()
    keys = [entry['listing_key'] for entry in records]
    if len(keys) != 54 or set(keys) != set(catalog) or len(set(keys)) != len(keys):
        raise ValueError('Exactly one image manifest per 54 catalog keys required')
    paths, hashes, sources, phashes = set(), set(), set(), []
    licenses, providers = Counter(), Counter()
    missing, absent, small, total, present = [], [], [], 0, set()
    licensed_records = []
    # Validate all declared provenance before considering absent local assets.
    for record in records:
        key = record['listing_key']
        if record['listing_title'] != catalog[key]:
            raise ValueError(f'{key}: listing title mismatch')
        if record.get('status') == 'missing':
            if not isinstance(record.get('reason'), str) or not record['reason'].strip():
                raise ValueError(f'{key}: missing reference requires reason')
            missing.append(key)
            continue
        if not REQUIRED <= record.keys() or record['source_type'] != 'licensed':
            raise ValueError(f'{key}: licensed manifest fields missing')
        for field in REQUIRED - {'width','height','byte_size'}:
            if not isinstance(record[field], str) or not record[field].strip():
                raise ValueError(f'{key}: malformed metadata {field}')
        filename = record['local_filename']
        path = (BASE/filename).resolve()
        if not path.is_relative_to((BASE/'images').resolve()) or path.suffix != '.webp' or path.stem != key:
            raise ValueError(f'{key}: unsafe/non-key image path')
        if filename in paths:
            raise ValueError(f'{key}: duplicate filename')
        paths.add(filename)
        if type(record['width']) is not int or type(record['height']) is not int or (record['width'],record['height']) != (1200,900):
            raise ValueError(f'{key}: format/dimensions mismatch')
        if type(record['byte_size']) is not int or record['byte_size'] <= 0 or not re.fullmatch(r'[0-9a-f]{64}',record['sha256']):
            raise ValueError(f'{key}: malformed size/hash metadata')
        for field in ('source_page_url','original_media_url','license_url'):
            url = urlparse(record[field])
            if url.scheme not in {'http','https'} or not url.hostname:
                raise ValueError(f'{key}: malformed metadata {field}')
        try:
            checked = datetime.fromisoformat(record['checked_at'].replace('Z','+00:00'))
            if checked.tzinfo is None:
                raise ValueError('timezone required')
        except ValueError as error:
            raise ValueError(f'{key}: malformed checked_at metadata') from error
        license_name = record['license_name']
        allowed = {f'{family} {version}' for family in ('CC BY','CC BY-SA') for version in ('2.0','2.5','3.0','4.0')}
        allowed |= {'CC0','CC0 1.0','Public domain','Public Domain','Pexels License','Unsplash License'}
        if license_name not in allowed:
            raise ValueError(f'{key}: unsupported license {license_name}')
        if record['sha256'] in hashes or record['source_page_url'] in sources:
            raise ValueError(f'{key}: exact image/source duplicate')
        hashes.add(record['sha256']); sources.add(record['source_page_url'])
        licensed_records.append((record,path))
    for record,path in licensed_records:
        key,filename = record['listing_key'],record['local_filename']
        declared_path = BASE/filename
        if not path.exists():
            if declared_path.is_symlink():
                raise ValueError(f'{key}: image path is not a regular file')
            if allow_missing_files:
                missing.append(key); absent.append(key)
                continue
            raise ValueError(f'{key}: missing image file')
        if not path.is_file():
            raise ValueError(f'{key}: image path is not a regular file')
        data = path.read_bytes()
        if data[:4] != b'RIFF' or data[8:12] != b'WEBP':
            raise ValueError(f'{key}: invalid WebP signature')
        digest = hashlib.sha256(data).hexdigest()
        if digest != record['sha256'] or len(data) != record['byte_size']:
            raise ValueError(f'{key}: hash/size mismatch')
        with Image.open(path) as image:
            image.load()
            if image.format != 'WEBP' or image.size != (1200,900):
                raise ValueError(f'{key}: format/dimensions mismatch')
            if image.getexif() or any(name in image.info for name in ('exif','xmp','icc_profile')):
                raise ValueError(f'{key}: identifying/embedded metadata present')
            phashes.append((key,difference_hash(image)))
        present.add(filename)
        licenses[record['license_name']] += 1
        providers['Wikimedia Commons' if 'commons.wikimedia.org' in record['source_page_url'] else 'Pexels' if 'pexels.com' in record['source_page_url'] else 'Unsplash' if 'unsplash.com' in record['source_page_url'] else 'Other'] += 1
        total += len(data)
        if len(data) < 100_000 or len(data) > 350_000:
            small.append({'listing_key':key,'byte_size':len(data)})
    actual = {str(path.relative_to(BASE)) for path in (BASE/'images').rglob('*') if path.is_file() or path.is_symlink()}
    if actual != present:
        raise ValueError(f'Orphan/missing files: {sorted(actual.symmetric_difference(present))}')
    candidates = [{'first':key,'second':other,'distance':(phash ^ otherhash).bit_count()} for i,(key,phash) in enumerate(phashes) for other,otherhash in phashes[i+1:] if (phash ^ otherhash).bit_count() <= 20]
    return {'catalog_keys':len(catalog),'manifest_entries':len(records),'images':len(present),'missing':missing,'absent_files':absent,'licenses':dict(licenses),'sources':dict(providers),'total_bytes':total,'outside_soft_size_target':small,'near_duplicate_candidates':candidates,'perceptual_hash':'256-bit dHash; Hamming distance <=20 triaged visually'}

if __name__ == '__main__':
    print(json.dumps(validate_images(),indent=2))
