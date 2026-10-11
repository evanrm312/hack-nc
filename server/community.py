"""Centralized club visibility and the deferred reservation gate."""
from sqlalchemy import or_
from .db import db, utcnow
from .errors import ApiError, not_found
from .models import ClubMembership, Exchange, Listing, OfferRevision
from .reservation import reserve_listing


def membership(club_id, profile_id):
    if not club_id or not profile_id:
        return None
    return db.session.scalar(db.select(ClubMembership).where(
        ClubMembership.club_id == club_id, ClubMembership.profile_id == profile_id))


def listing_visibility(profile):
    if profile is None:
        return Listing.club_id.is_(None)
    club_ids = db.select(ClubMembership.club_id).where(ClubMembership.profile_id == profile.id)
    return or_(Listing.club_id.is_(None), Listing.club_id.in_(club_ids))


def require_listing_access(listing, profile):
    if listing is None or (listing.club_id and not membership(listing.club_id, profile.id if profile else None)):
        raise not_found("listing")


def require_exchange_members(exchange):
    if exchange.club_id and any(not membership(exchange.club_id, p) for p in exchange.participant_ids):
        raise not_found("exchange")


def initialize_club(exchange, listing):
    exchange.club_id = listing.club_id
    exchange.club_review_state = "awaiting_participants" if listing.club_id else "not_required"
    require_exchange_members(exchange)


def reset_review(exchange):
    if exchange.club_id:
        exchange.club_review_state = "awaiting_participants"
        exchange.club_review_note = None
        exchange.club_reviewed_by = None
        exchange.club_reviewed_at = None
        exchange.club_review_version = None


def finalize_acceptance(exchange):
    """Same atomic reservation for public exchanges or the authorized review path."""
    require_exchange_members(exchange)
    if exchange.club_id:
        if exchange.club_review_state == "changes_requested":
            raise ApiError(409, "changes_requested", "Propose a new offer before accepting again")
        exchange.club_review_state = "pending"
        return
    reserve_accepted(exchange)


def reserve_accepted(exchange):
    if not reserve_listing(db.session, exchange.listing_id, exchange.id):
        raise ApiError(409, "reservation_conflict", "Another exchange reserved this listing; no funds were charged")
    exchange.status = "scheduled" if exchange.mode == "service" else "reserved"


def current_offer(exchange):
    return db.session.scalar(db.select(OfferRevision).where(
        OfferRevision.exchange_id == exchange.id, OfferRevision.version == exchange.current_offer_revision))


def manager_summary(exchange):
    from .models import Profile
    offer = current_offer(exchange)
    # Never serialize OfferRevision wholesale: locations, evidence and free text
    # condition snapshots have no place in the administrative response.
    fields = ("service_price_cents", "service_duration_minutes", "service_scheduled_at") if exchange.mode == "service" else (
        "sale_price_cents", "rental_fee_cents", "agreed_item_value_cents", "deposit_cents",
        "lower_deposit_acknowledged", "pickup_at", "return_deadline")
    terms = offer.to_dict() if offer else {}
    return {"id": exchange.id, "listing_title": db.session.get(Listing, exchange.listing_id).title,
            "participants": {"owner": db.session.get(Profile, exchange.owner_id).display_name,
                             "requester": db.session.get(Profile, exchange.requester_id).display_name},
            "mode": exchange.mode, "status": exchange.status,
            "club_review_state": exchange.club_review_state, "club_review_note": exchange.club_review_note,
            "offer_version": exchange.current_offer_revision,
            "agreed_terms": {k: terms.get(k) for k in fields}}
