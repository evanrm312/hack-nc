"""Validate the real reference fixture and failures without network/database access."""
import copy
import importlib.util
from pathlib import Path
import pytest

BASE = Path(__file__).resolve().parent

def load(name):
    spec = importlib.util.spec_from_file_location(name, BASE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@pytest.fixture
def catalog():
    return load('validate_catalog').validate()[0]

@pytest.fixture
def validator():
    return load('validate_images')

def test_real_catalog_images_have_complete_provenance_and_no_duplicates(catalog, validator):
    result = validator.validate_images(catalog)
    assert result['manifest_entries'] == 54
    assert result['images'] == 52
    assert set(result['missing']) == {'clothing-event-tablecloths','dorm-storage-bins-pair'}
    assert result['near_duplicate_candidates'] == []
    assert result['total_bytes'] > 0

@pytest.mark.parametrize('mutation,error',[
    ('duplicate_key','Exactly one image manifest'),
    ('bad_hash','hash/size mismatch'),
    ('wrong_dimensions','format/dimensions mismatch'),
    ('source_duplicate','exact image/source duplicate'),
    ('unsafe_path','unsafe/non-key image path'),
    ('noncommercial_license','unsupported license'),
    ('missing_reason','missing reference requires reason'),
])
def test_invalid_manifest_is_rejected(catalog,validator,monkeypatch,mutation,error):
    records = copy.deepcopy(validator.manifests())
    licensed = [entry for entry in records if entry.get('source_type') == 'licensed']
    if mutation == 'duplicate_key': records[-1]['listing_key'] = records[0]['listing_key']
    elif mutation == 'bad_hash': licensed[0]['sha256'] = '0' * 64
    elif mutation == 'wrong_dimensions': licensed[0]['width'] = 600
    elif mutation == 'source_duplicate': licensed[1]['source_page_url'] = licensed[0]['source_page_url']
    elif mutation == 'unsafe_path': licensed[0]['local_filename'] = '../outside.webp'
    elif mutation == 'noncommercial_license': licensed[0]['license_name'] = 'CC BY-NC 4.0'
    else: next(entry for entry in records if entry.get('status') == 'missing').pop('reason')
    monkeypatch.setattr(validator,'manifests',lambda:records)
    with pytest.raises(ValueError,match=error): validator.validate_images(catalog)

@pytest.fixture
def isolated_images(validator,monkeypatch,tmp_path):
    """Copy references so absence/tampering tests never alter repository assets."""
    import shutil
    records = validator.manifests()
    shutil.copytree(BASE/'images',tmp_path/'images')
    monkeypatch.setattr(validator,'BASE',tmp_path)
    monkeypatch.setattr(validator,'manifests',lambda:copy.deepcopy(records))
    return records,tmp_path

def test_missing_file_is_strict_by_default_but_seed_can_continue(catalog,validator,isolated_images):
    records,directory = isolated_images
    record = next(entry for entry in records if entry.get('source_type')=='licensed')
    original = validator.validate_images(catalog)
    (directory/record['local_filename']).unlink()
    with pytest.raises(ValueError,match='missing image file'):
        validator.validate_images(catalog)
    result = validator.validate_images(catalog,allow_missing_files=True)
    assert result['images'] == 51
    assert result['absent_files'] == [record['listing_key']]
    assert record['listing_key'] in result['missing']
    assert result['total_bytes'] == original['total_bytes']-record['byte_size']

@pytest.mark.parametrize('problem',['tampered_present','directory','bad_absent_license','duplicate_absent_hash','duplicate_absent_source','orphan','escape'])
def test_tolerant_seed_mode_still_rejects_tampering(catalog,validator,isolated_images,monkeypatch,problem):
    records,directory = isolated_images
    licensed = [entry for entry in records if entry.get('source_type')=='licensed']
    first,second = licensed[:2]
    first_path = directory/first['local_filename']
    first_path.unlink()
    if problem=='tampered_present':
        (directory/second['local_filename']).write_bytes(b'not a WebP')
        error='invalid WebP signature'
    elif problem=='directory': first_path.mkdir();error='not a regular file'
    elif problem=='bad_absent_license': first['license_name']='CC BY-NC 4.0';error='unsupported license'
    elif problem=='duplicate_absent_hash': first['sha256']=second['sha256'];error='exact image/source duplicate'
    elif problem=='duplicate_absent_source': first['source_page_url']=second['source_page_url'];error='exact image/source duplicate'
    elif problem=='orphan': (directory/'images'/'extra.webp').write_bytes(b'orphan');error='Orphan/missing files'
    else: first_path.symlink_to(directory/'outside.webp');error='unsafe/non-key image path'
    monkeypatch.setattr(validator,'manifests',lambda:copy.deepcopy(records))
    with pytest.raises(ValueError,match=error):validator.validate_images(catalog,allow_missing_files=True)
