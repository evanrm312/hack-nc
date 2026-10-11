"""Private participant meeting context, retained for at most 24 hours."""
from datetime import timedelta
from math import radians, sin, cos, asin, sqrt
from flask import Blueprint, jsonify
from ..auth import current_profile, require_verified_user
from ..db import db, utcnow
from ..errors import ApiError, forbidden, not_found, validation_error
from ..models import Exchange, ExchangeLocation, MeetingSpot, Profile
from ..validation import json_body, FieldErrors, string
bp = Blueprint('locations',__name__)

@bp.after_request
def private(response):
    response.headers['Cache-Control']='private, no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    return response

def participant(exchange_id):
    exchange=db.session.get(Exchange,exchange_id)
    if exchange is None: raise not_found('exchange')
    if current_profile().id not in exchange.participant_ids: raise forbidden('Only participants can access locations')
    return exchange

def distance(a,b):
    x,y=map(radians,a);u,v=map(radians,b)
    return 6371000*2*asin(min(1,sqrt(sin((u-x)/2)**2+cos(x)*cos(u)*sin((v-y)/2)**2)))

@bp.get('/api/exchanges/<exchange_id>/locations')
@require_verified_user
def locations(exchange_id):
    exchange=participant(exchange_id)
    rows=db.session.scalars(db.select(ExchangeLocation).where(ExchangeLocation.exchange_id==exchange_id,
        ExchangeLocation.expires_at>utcnow())).all() if exchange.status not in ('completed','cancelled','disputed') else []
    spots=[s.to_dict() for s in db.session.scalars(db.select(MeetingSpot).where(MeetingSpot.is_active.is_(True)).order_by(MeetingSpot.label))]
    positions=[(r.latitude,r.longitude) for r in rows if r.latitude is not None and r.longitude is not None]
    ranked=len(positions)==2
    preferences=[db.session.get(Profile,p).preferred_meeting_spot_id for p in exchange.participant_ids]
    for spot in spots:
        spot['preferred_by_participant']=spot['id'] in preferences
        if ranked and spot.get('latitude') is not None:
            distances=[round(distance(p,(spot['latitude'],spot['longitude']))) for p in positions]
            spot['straight_line_distances_m']=distances
    if ranked: spots.sort(key=lambda s:(max(s.get('straight_line_distances_m',[float('inf')])),sum(s.get('straight_line_distances_m',[float('inf')]))))
    return jsonify(locations=[r.to_dict() for r in rows],meeting_spots=spots,ranking='straight_line_estimate' if ranked else 'unranked')

@bp.put('/api/exchanges/<exchange_id>/locations/me')
@require_verified_user
def update_location(exchange_id):
    exchange=participant(exchange_id)
    db.session.execute(db.update(Exchange).where(Exchange.id==exchange_id).values(updated_at=Exchange.updated_at))
    db.session.refresh(exchange)
    if exchange.status not in ('negotiating','reserved','scheduled','on_loan','return_pending'):
        raise ApiError(409,'invalid_transition','This exchange is closed')
    body=json_body();errors=FieldErrors()
    landmark=string(body.get('landmark'),'landmark',errors,max_len=120)
    lat,lon=body.get('latitude'),body.get('longitude')
    if lat is not None or lon is not None:
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) for v in (lat,lon)) or not (35.89<=lat<=35.93 and -79.08<=lon<=-79.02):
            errors.add('coordinates','choose a location within the UNC campus area')
    if 'participant_id' in body: errors.add('participant_id','you may update only your own location')
    errors.raise_if_any()
    # Expired data is removed on any location write, never returned by reads.
    db.session.execute(db.delete(ExchangeLocation).where(ExchangeLocation.expires_at<=utcnow()))
    row=db.session.scalar(db.select(ExchangeLocation).where(ExchangeLocation.exchange_id==exchange_id,
        ExchangeLocation.participant_id==current_profile().id))
    if row is None:
        row=ExchangeLocation(exchange_id=exchange_id,participant_id=current_profile().id);db.session.add(row)
    row.landmark=landmark
    row.latitude=round(lat,4) if lat is not None else None
    row.longitude=round(lon,4) if lon is not None else None
    row.expires_at=utcnow()+timedelta(hours=24)
    db.session.commit()
    return jsonify(location=row.to_dict())

@bp.delete('/api/exchanges/<exchange_id>/locations/me')
@require_verified_user
def clear_location(exchange_id):
    participant(exchange_id)
    db.session.execute(db.delete(ExchangeLocation).where(ExchangeLocation.exchange_id==exchange_id,
        ExchangeLocation.participant_id==current_profile().id));db.session.commit()
    return jsonify(ok=True)
