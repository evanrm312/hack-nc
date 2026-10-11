"""Public community profile with aggregates and explicit minimal history opt-in."""
from io import BytesIO
from flask import Blueprint, current_app, jsonify, request
from ..auth import current_profile, require_verified_user
from ..db import db, iso_utc
from ..errors import not_found, validation_error
from ..models import Profile, Exchange, Listing, Review
from ..storage import get_storage, read_image_upload
from ..exchanges.images import _decode

bp = Blueprint('profiles', __name__)


def public_profile(profile):
    result = profile.to_public_dict()
    ratings = db.session.execute(db.select(db.func.avg(Review.stars), db.func.count(Review.id))
        .join(Exchange, Exchange.id == Review.exchange_id)
        .where(Review.reviewee_id == profile.id, Exchange.status == 'completed')).one()
    result['rating'] = {'average': float(ratings[0]) if ratings[0] is not None else None, 'review_count': ratings[1]}
    rows = db.session.execute(db.select(Exchange, Listing).join(Listing, Listing.id == Exchange.listing_id)
        .where(Exchange.status == 'completed', db.or_(Exchange.owner_id == profile.id, Exchange.requester_id == profile.id))
        .order_by(Exchange.updated_at.desc(), Exchange.id)).all()
    counts = {'bought': 0, 'sold_lent_provided': 0, 'borrowed': 0, 'services': 0}
    history = []
    for exchange, listing in rows:
        owner = exchange.owner_id == profile.id
        if owner:
            counts['sold_lent_provided'] += 1
        elif exchange.mode == 'sale': counts['bought'] += 1
        elif exchange.mode == 'borrow': counts['borrowed'] += 1
        if exchange.mode == 'service': counts['services'] += 1
        # Restricted titles stay private even after a history opt-in.
        if listing.club_id is None:
            history.append({'listing_title': listing.title, 'mode': exchange.mode,
                            'role': 'owner' if owner else 'requester', 'completed_at': iso_utc(exchange.updated_at)})
    result['completed_counts'] = counts
    result['transaction_history'] = history if profile.show_transaction_history else None
    return result


@bp.get('/api/profiles/<profile_id>')
def get_profile(profile_id):
    profile = db.session.get(Profile, profile_id)
    if profile is None:
        raise not_found('profile')
    return jsonify({'profile': public_profile(profile)})


@bp.post('/api/me/avatar')
@require_verified_user
def avatar():
    upload = request.files.get('photo')
    if upload is None:
        raise validation_error({'photo': "multipart field 'photo' is required"})
    limit = min(current_app.config['MAX_UPLOAD_BYTES'], 1024 * 1024)
    data, content_type, _ = read_image_upload(upload.stream, limit)
    if upload.mimetype != content_type:
        raise validation_error({'photo': 'MIME type must match JPEG, PNG or WebP content'})
    # Decode completely, reject animated/bomb images, orient, resize and strip
    # metadata before sending the public avatar through the shared adapter.
    output = BytesIO()
    with _decode(data) as image:
        image.thumbnail((512, 512))
        with image.convert('RGB') as rgb:
            rgb.save(output, format='WEBP', quality=85)
    output.seek(0)
    storage = get_storage()
    stored = storage.save('public', output, limit)
    profile = current_profile()
    db.session.execute(db.update(Profile).where(Profile.id == profile.id).values(display_name=Profile.display_name))
    db.session.refresh(profile)
    old = profile.avatar_path
    profile.avatar_path = stored.path
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        storage.delete('public', stored.path)
        raise
    if old:
        try:
            storage.delete('public', old)
        except Exception:
            current_app.logger.warning('Previous avatar cleanup failed')
    return jsonify({'profile': profile.to_me_dict()})


@bp.after_request
def cache(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response
