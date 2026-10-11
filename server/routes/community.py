"""Code-based membership and privacy-limited administrative review."""
from flask import Blueprint, jsonify
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash
from ..auth import current_profile, require_verified_user
from ..db import db, utcnow
from ..errors import ApiError, forbidden, not_found, validation_error
from ..models import Club, ClubMembership, Exchange, Listing
from ..community import membership, current_offer, manager_summary, require_exchange_members, reserve_accepted
from ..validation import FieldErrors, json_body, string

bp = Blueprint("community", __name__)


def _club_access(club_id, manager=False):
    row = membership(club_id, current_profile().id)
    if row is None:
        raise not_found("club")
    if manager and row.role != "manager":
        raise forbidden("Only club managers can review exchanges")
    return row.club


@bp.get('/api/clubs/me')
@require_verified_user
def my_clubs():
    return jsonify({"memberships": current_profile().public_clubs()})


@bp.post('/api/clubs/join')
@require_verified_user
def join():
    body = json_body()
    code = body.get('code')
    if not isinstance(code, str) or not 1 <= len(code) <= 128:
        raise ApiError(400, 'invalid_club_code', 'Unable to join with that code')
    # All seeded hashes are checked; failure gives no club existence hint.
    clubs = db.session.scalars(db.select(Club).order_by(Club.id)).all()
    matches = [club for club in clubs if check_password_hash(club.code_hash, code)]
    if len(matches) != 1:
        raise ApiError(400, 'invalid_club_code', 'Unable to join with that code')
    club = matches[0]
    row = membership(club.id, current_profile().id)
    if row is None:
        row = ClubMembership(club_id=club.id, profile_id=current_profile().id, role='member')
        db.session.add(row)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            row = membership(club.id, current_profile().id)
            if row is None:
                raise
    return jsonify({"membership": {"club": club.to_dict(), "role": row.role}})


@bp.get('/api/clubs/<club_id>')
@require_verified_user
def club_detail(club_id):
    return jsonify({"club": _club_access(club_id).to_dict()})


@bp.get('/api/clubs/<club_id>/exchanges')
@require_verified_user
def manager_exchanges(club_id):
    _club_access(club_id, manager=True)
    rows = db.session.scalars(db.select(Exchange).where(Exchange.club_id == club_id)
        .order_by(Exchange.updated_at.desc())).all()
    return jsonify({"exchanges": [manager_summary(row) for row in rows]})


@bp.post('/api/clubs/<club_id>/exchanges/<exchange_id>/review')
@require_verified_user
def review(club_id, exchange_id):
    _club_access(club_id, manager=True)
    body = json_body()
    if body.get('decision') not in ('approve', 'request_changes'):
        raise validation_error({'decision': 'must be approve or request_changes'})
    errors = FieldErrors()
    note = string(body.get('note'), 'note', errors, max_len=300)
    version = body.get('version')
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        errors.add('version', 'current offer version required')
    if body['decision'] == 'request_changes' and not note:
        errors.add('note', 'a short explanation is required')
    errors.raise_if_any()
    try:
        db.session.execute(db.update(Exchange).where(Exchange.id == exchange_id,
            Exchange.club_id == club_id).values(updated_at=Exchange.updated_at))
        exchange = db.session.get(Exchange, exchange_id, populate_existing=True)
        if exchange is None or exchange.club_id != club_id:
            raise not_found('exchange')
        if current_profile().id in exchange.participant_ids:
            raise forbidden('A participant cannot review their own exchange')
        require_exchange_members(exchange)
        if version != exchange.current_offer_revision:
            raise ApiError(409, 'stale_offer', 'Review the latest offer revision')
        if body['decision'] == 'approve' and exchange.club_review_state == 'approved':
            db.session.commit()
            return jsonify({'exchange': manager_summary(exchange)})
        if exchange.status != 'negotiating' or exchange.club_review_state != 'pending':
            raise ApiError(409, 'review_not_ready', 'Both participants must accept the latest offer first')
        offer = current_offer(exchange)
        if not offer or not offer.owner_accepted_at or not offer.requester_accepted_at:
            raise ApiError(409, 'review_not_ready', 'Both participants must accept the latest offer first')
        if body['decision'] == 'approve':
            if exchange.mode == 'service':
                from ..exchanges.service import _fits_window
                from ..models import MeetingSpot
                listing = db.session.get(Listing, exchange.listing_id, populate_existing=True)
                if not _fits_window(listing, offer.service_scheduled_at, offer.service_duration_minutes):
                    raise ApiError(409,'schedule_unavailable','Propose a new service time')
                if offer.service_delivery == 'in_person':
                    spot = db.session.get(MeetingSpot, offer.service_meeting_spot_id)
                    if not spot or not spot.is_active:
                        raise ApiError(409,'schedule_unavailable','Choose an active meeting spot')
            else:
                from ..exchanges.offers import terms_from_offer, validate_terms
                validate_terms(terms_from_offer(offer), exchange.mode, complete=True)
                if offer.uncovered_value_cents and not offer.lower_deposit_acknowledged:
                    raise ApiError(409,'review_not_ready','Lender acknowledgment required')
            reserve_accepted(exchange)
            exchange.club_review_state = 'approved'
        else:
            exchange.club_review_state = 'changes_requested'
        exchange.club_review_note = note
        exchange.club_reviewed_by = current_profile().id
        exchange.club_reviewed_at = utcnow()
        exchange.club_review_version = version
        db.session.commit()
        return jsonify({'exchange': manager_summary(exchange)})
    except Exception:
        db.session.rollback()
        raise


@bp.after_request
def private(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response
