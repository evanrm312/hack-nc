"""Bounded, deterministic discovery. Never exposes the underlying private signals."""
from collections import Counter
from datetime import timedelta, timezone, datetime
from flask import Blueprint, jsonify
from ..auth import current_profile, optional_user
from ..db import db, utcnow
from ..community import listing_visibility
from ..models import Listing, NeedRequest, Exchange
from ..intelligence.matching import match_listings

bp = Blueprint('discovery', __name__, url_prefix='/api')

def _aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

def _available(listing, now):
    # SQL handles visibility, status, reservation and ownership before its limit.
    # Discard expired availability before ranking; unknown dates stay unknown.
    ends = [w.get('end') for w in (listing.service_available_windows or [])] if listing.allowed_modes == ['service'] else [(listing.availability or {}).get('available_until')]
    if not any(ends):
        return True
    try:
        return any(datetime.fromisoformat(e.replace('Z', '+00:00')) > now for e in ends if e)
    except (ValueError, TypeError):
        return False  # invalid legacy dates cannot become recommendations

def recommendations(profile=None):
    now = utcnow()
    query = db.select(Listing).where(listing_visibility(profile), Listing.status == 'available', Listing.active_exchange_id.is_(None),
        db.or_(Listing.publication_required.is_(False), Listing.public_photo_path.is_not(None)))
    if profile:
        query = query.where(Listing.owner_id != profile.id)
    rows = db.session.scalars(query.order_by(Listing.created_at.desc(), Listing.id.asc()).limit(200)).unique().all()
    rows = [l for l in rows if _available(l, now)]
    requests, history = [], []
    if profile:
        requests = db.session.scalars(db.select(NeedRequest).where(NeedRequest.requester_id == profile.id,
            NeedRequest.status.in_(['draft','open']), NeedRequest.updated_at >= now-timedelta(days=30),
            db.or_(NeedRequest.needed_by.is_(None),NeedRequest.needed_by >= now)).order_by(NeedRequest.updated_at.desc(),NeedRequest.id.asc()).limit(10)).unique().all()
        history = db.session.execute(db.select(Listing.category,Exchange.mode).join(Exchange,Exchange.listing_id == Listing.id).where(
            Exchange.requester_id == profile.id, Exchange.status == 'completed').order_by(Exchange.updated_at.desc(),Exchange.id.asc()).limit(20)).all()
    data = {l.id:l.to_dict() for l in rows}
    signals = {}
    excluded = set()
    for req in requests:
        category=(req.normalized or {}).get('category')
        # Reuse Aarush's enforced compatibility checks without editing intelligence.
        matched=match_listings(req.to_owner_dict(),list(data.values()))
        for bucket,weight,reason in [('confirmed',100,'Fits a recent request'),('needs_confirmation',65,'Related to a recent request · Confirm details')]:
            for entry in matched[bucket]:
                key=entry['listing_id']
                if weight > signals.get(key,(0,'',None))[0]: signals[key]=(weight,reason,entry['mode'])
        # Never suggest a same-category incompatible mode or known failed constraint
        # as a personalized alternative. Unknown constraints remain conditional.
        excluded.update(e['listing_id'] for e in matched['rejected'] if data[e['listing_id']]['category'] == category)
    history_pairs = set(history)
    ranked=[]
    for l in rows:
        if l.id in excluded and l.id not in signals:
            continue
        weight,reason,mode=signals.get(l.id,(0,'Recently listed',None))
        if not weight:
            pair=next(((category,m) for category,m in sorted(history_pairs) if category==l.category and m in l.allowed_modes),None)
            if pair: weight,reason,mode=25,'Related to your completed '+{'sale':'purchases','borrow':'loans','service':'services'}[pair[1]],pair[1]
        age=max(0,(now-_aware(l.created_at)).total_seconds()/86400)
        ranked.append({'listing':data[l.id],'reason':reason,'mode':mode,'weight':weight+10*max(0,1-age/30),'created':_aware(l.created_at)})
    selected=[]; categories=Counter()
    while ranked and len(selected)<6:
        ranked.sort(key=lambda x:(-(x['weight']-35*categories[x['listing']['category']]),-x['created'].timestamp(),x['listing']['id']))
        entry=ranked.pop(0);categories[entry['listing']['category']]+=1
        selected.append({k:entry[k] for k in ('listing','reason','mode')})
    return {'items':selected,'personalized':any(x['reason']!='Recently listed' for x in selected),'label':'For you' if any(x['reason']!='Recently listed' for x in selected) else 'Browsing suggestions'}

@bp.get('/recommendations')
@optional_user
def discovery():
    response=jsonify(recommendations(current_profile()))
    response.headers['Cache-Control']='private, no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    return response
