"""Scoped creation keys prevent retrying a lost response from duplicating records."""
import hashlib
import json
from flask import request
from sqlalchemy.exc import IntegrityError
from .db import db
from .errors import validation_error, ApiError

def creation(model, owner_field, owner_id, body):
    key=request.headers.get('Idempotency-Key')
    if key is None: return None,None,None
    if not isinstance(key,str) or not 8<=len(key)<=80 or not all(c.isalnum() or c in '-_' for c in key):
        raise validation_error({'idempotency_key':'use an opaque key of 8–80 letters, digits, hyphens or underscores'})
    from .models import Profile
    # Lock this creator before checking a retry key, including on SQLite.
    db.session.execute(db.update(Profile).where(Profile.id==owner_id).values(display_name=Profile.display_name))
    fingerprint=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    existing=db.session.scalar(db.select(model).where(getattr(model,owner_field)==owner_id,model.creation_key==key))
    if existing and existing.creation_fingerprint!=fingerprint:
        raise ApiError(409,'idempotency_conflict','This retry key belongs to a different submission')
    return existing,key,fingerprint

def commit_creation(row, owner_field):
    try: db.session.commit();return row
    except IntegrityError:
        key,fingerprint,owner=row.creation_key,row.creation_fingerprint,getattr(row,owner_field)
        db.session.rollback()
        if not key: raise
        existing=db.session.scalar(db.select(type(row)).where(getattr(type(row),owner_field)==owner,type(row).creation_key==key))
        if existing is None or existing.creation_fingerprint!=fingerprint: raise
        return existing
