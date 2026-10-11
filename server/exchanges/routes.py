"""Private, persisted negotiation, evidence, pickup, and return."""

from __future__ import annotations

from functools import wraps

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import and_, or_, update

from ..auth import current_profile, require_verified_user
from ..community import require_listing_access, require_exchange_members, initialize_club, reset_review, finalize_acceptance, listing_visibility, membership
from ..idempotency import creation, commit_creation
from ..db import db, utcnow
from ..errors import ApiError, forbidden, not_found, validation_error
from ..models import (
    Evidence,
    Exchange,
    Listing,
    MeetingSpot,
    Message,
    NeedRequest,
    OfferRevision,
    Profile,
    Review,
)
from ..models.review import REVIEW_FIELDS
from ..reservation import mark_listing_sold, release_listing, reserve_listing
from ..storage import authorize_private_read, get_storage
from ..validation import FieldErrors, datetime_utc, json_body, string
from .offers import (
    TERM_FIELDS,
    initial_terms,
    same_terms,
    terms_from_offer,
    validate_terms,
)
from .lifecycle import (
    PICKUP_STAGES, acknowledge_and_confirm, confirmations_for, ensure_photos_open,
    invalid_transition, require_pickup_photos, require_return_photos,
)
from . import service

bp = Blueprint("exchanges", __name__, url_prefix="/api/exchanges")
SIMULATION_NOTICE = "Simulated: no real funds are reserved or charged."


def _deposit_status(exchange):
    state = "simulated_pending"
    if exchange.mode == "borrow" and exchange.status in ("reserved", "on_loan", "return_pending", "disputed"):
        state = "simulated_held"
    elif exchange.status in ("completed", "cancelled"):
        state = "simulated_released"
    return {"state": state, "label": SIMULATION_NOTICE}


def _transaction(view):
    """Roll back failed actions, including an unsuccessful reservation."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except Exception:
            db.session.rollback()
            raise
    return wrapped


def _participant(exchange_id: str, *, lock: bool = False) -> Exchange:
    user_id = current_profile().id
    if lock:
        # A no-op UPDATE takes a row lock on Postgres and a write lock on SQLite.
        # Acquire it before reading state so simultaneous edits/acceptances use
        # the latest revision. Unlike SELECT FOR UPDATE, this works on SQLite.
        db.session.execute(
            update(Exchange)
            .where(Exchange.id == exchange_id,
                   or_(Exchange.owner_id == user_id, Exchange.requester_id == user_id))
            .values(updated_at=Exchange.updated_at)
            .execution_options(synchronize_session=False)
        )
    exchange = db.session.get(Exchange, exchange_id, populate_existing=True)
    if exchange is None:
        raise not_found("exchange")
    if user_id not in exchange.participant_ids:
        raise forbidden("Only participants can access this exchange")
    require_exchange_members(exchange)
    return exchange


def _current_offer(exchange: Exchange) -> OfferRevision:
    offer = db.session.scalar(
        db.select(OfferRevision).where(
            OfferRevision.exchange_id == exchange.id,
            OfferRevision.version == exchange.current_offer_revision,
        ).execution_options(populate_existing=True)
    )
    if offer is None:
        raise ApiError(409, "offer_missing", "This exchange has no current offer")
    return offer


def _negotiating(exchange: Exchange) -> None:
    if exchange.status != "negotiating":
        raise ApiError(409, "exchange_locked", "Offer terms are locked after negotiation")


def _available(listing: Listing) -> None:
    if listing.status != "available" or listing.active_exchange_id is not None:
        raise ApiError(409, "reservation_conflict", "This item is no longer available")


def _is_service(exchange_id: str) -> bool:
    """Route by persisted mode; the selected handler enforces participant access."""
    exchange = db.session.get(Exchange, exchange_id)
    return exchange is not None and exchange.mode == "service"


@bp.after_request
def _private_response(response):
    # Authenticated messages, precise meeting times, and evidence must not be cached.
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.get("")
@require_verified_user
def list_exchanges():
    user_id = current_profile().id
    rows = db.session.execute(
        db.select(Exchange, Listing, OfferRevision).join(Listing, Exchange.listing_id == Listing.id)
        .outerjoin(OfferRevision, and_(OfferRevision.exchange_id == Exchange.id,
                                      OfferRevision.version == Exchange.current_offer_revision))
        .where(or_(Exchange.owner_id == user_id, Exchange.requester_id == user_id))
        .order_by(Exchange.updated_at.desc(), Exchange.id)
    ).all()
    rows = [(e, l, o) for e, l, o in rows if not e.club_id or all(
        membership(e.club_id, pid) for pid in e.participant_ids)]
    if not rows:
        return jsonify({"exchanges": []})
    # Fetch dashboard records in batches, always scoped to the caller's exchanges.
    exchange_ids = [exchange.id for exchange, _, _ in rows]
    participant_ids = {user_id for exchange, _, _ in rows for user_id in exchange.participant_ids}
    profiles = {profile.id: profile.to_public_dict() for profile in db.session.scalars(
        db.select(Profile).where(Profile.id.in_(participant_ids))
    )}
    photos_by_exchange = {exchange_id: [] for exchange_id in exchange_ids}
    for photo in db.session.scalars(db.select(Evidence).where(Evidence.exchange_id.in_(exchange_ids))
                                   .order_by(Evidence.created_at, Evidence.id)):
        photos_by_exchange[photo.exchange_id].append(photo)
    reviews = {review.exchange_id: review.to_dict() for review in db.session.scalars(
        db.select(Review).where(Review.exchange_id.in_(exchange_ids), Review.reviewer_id == user_id)
    )}
    spot_ids = {spot_id for _, _, offer in rows if offer is not None
                for spot_id in (offer.pickup_meeting_spot_id, offer.return_meeting_spot_id) if spot_id}
    spots = {spot.id: spot.to_dict() for spot in db.session.scalars(
        db.select(MeetingSpot).where(MeetingSpot.id.in_(spot_ids))
    )}
    exchanges = []
    for exchange, listing, offer in rows:
        data = exchange.to_dict()
        listing_data = listing.to_dict()
        data["listing"] = {
            key: listing_data[key]
            for key in ("id", "title", "status", "public_photo_url")
        }
        photos = photos_by_exchange[exchange.id]
        data.update({
            "current_offer": offer.to_dict() if offer is not None else None,
            "participants": {"owner": profiles[exchange.owner_id], "requester": profiles[exchange.requester_id]},
            "pickup_meeting_spot": spots.get(offer.pickup_meeting_spot_id) if offer is not None else None,
            "return_meeting_spot": spots.get(offer.return_meeting_spot_id) if offer is not None else None,
            "confirmations": confirmations_for(exchange, "handoff", photos=photos)
                             + confirmations_for(exchange, "return", photos=photos),
            "evidence": [photo.to_dict() for photo in photos],
            "deposit_status": _deposit_status(exchange),
            "my_review": reviews.get(exchange.id),
            "can_review": exchange.status == "completed" and exchange.id not in reviews,
        })
        exchanges.append(data)
    return jsonify({"exchanges": exchanges})


@bp.post("")
@require_verified_user
@_transaction
def create_exchange():
    body = json_body()
    if body.get("mode") == "service":
        return service.create()
    existing,key,fingerprint=creation(Exchange,"requester_id",current_profile().id,body)
    if existing:
        require_exchange_members(existing)
        return jsonify({"exchange":existing.to_dict(),"current_offer":_current_offer(existing).to_dict()}),201
    errors = FieldErrors()
    listing_id = string(body.get("listing_id"), "listing_id", errors, required=True, max_len=32)
    mode = body.get("mode")
    if mode not in ("sale", "borrow"):
        errors.add("mode", "must be sale, borrow, or service")
    source_id = string(body.get("source_request_id"), "source_request_id", errors, max_len=32)
    errors.raise_if_any()
    listing = db.session.get(Listing, listing_id)
    require_listing_access(listing, current_profile())
    user_id = current_profile().id
    if listing.owner_id == user_id:
        raise forbidden("Start an exchange for another member's listing")
    _available(listing)
    if mode not in listing.allowed_modes:
        raise validation_error({"mode": "not offered by this listing"})
    if source_id:
        source = db.session.get(NeedRequest, source_id)
        if source is None or source.requester_id != user_id:
            raise not_found("request")
        if source.status not in ("draft", "open"):
            raise ApiError(409, "request_closed", "This request is closed")
        if mode not in (source.modes or []):
            raise validation_error({"source_request_id": "request does not include this exchange mode"})

    exchange = Exchange(
        listing_id=listing.id, owner_id=listing.owner_id, requester_id=user_id,
        source_request_id=source_id, mode=mode, status="negotiating", current_offer_revision=1,
        creation_key=key,creation_fingerprint=fingerprint,
    )
    initialize_club(exchange, listing)
    db.session.add(exchange)
    db.session.flush()
    offer = OfferRevision(
        exchange_id=exchange.id, version=1, created_by=user_id,
        **validate_terms(initial_terms(listing, mode), mode),
    )
    db.session.add(offer)
    exchange=commit_creation(exchange,"requester_id")
    return jsonify({"exchange": exchange.to_dict(), "current_offer": _current_offer(exchange).to_dict()}), 201


@bp.get("/<exchange_id>")
@require_verified_user
def get_exchange(exchange_id: str):
    if _is_service(exchange_id):
        return service.detail(exchange_id)
    exchange = _participant(exchange_id)
    offers = db.session.scalars(
        db.select(OfferRevision).where(OfferRevision.exchange_id == exchange.id)
        .order_by(OfferRevision.version)
    ).all()
    return jsonify({
        "exchange": exchange.to_dict(),
        "current_offer": _current_offer(exchange).to_dict(),
        "offers": [offer.to_dict() for offer in offers],
        "simulation_notice": SIMULATION_NOTICE,
        "deposit_status": _deposit_status(exchange),
        "confirmations": confirmations_for(exchange, "handoff") + confirmations_for(exchange, "return"),
        "max_upload_bytes": current_app.config["MAX_UPLOAD_BYTES"],
        "participants": {
            "owner": db.session.get(Profile, exchange.owner_id).to_public_dict(),
            "requester": db.session.get(Profile, exchange.requester_id).to_public_dict(),
        },
    })


@bp.get("/<exchange_id>/messages")
@require_verified_user
def list_messages(exchange_id: str):
    if _is_service(exchange_id):
        return service.messages(exchange_id)
    exchange = _participant(exchange_id)
    query = db.select(Message).where(Message.exchange_id == exchange.id)
    if "after" in request.args:
        errors = FieldErrors()
        after = datetime_utc(request.args["after"], "after", errors)
        errors.raise_if_any()
        # Inclusive: shared ISO serialization has second precision. The client
        # deduplicates by id so messages in the same second are never skipped.
        query = query.where(Message.created_at >= after)
    messages = db.session.scalars(query.order_by(Message.created_at, Message.id)).all()
    return jsonify({"messages": [message.to_dict() for message in messages]})


@bp.post("/<exchange_id>/messages")
@require_verified_user
@_transaction
def post_message(exchange_id: str):
    if _is_service(exchange_id):
        return service.post_message(exchange_id)
    exchange = _participant(exchange_id, lock=True)
    errors = FieldErrors()
    body = string(json_body().get("body"), "body", errors, required=True, max_len=4000)
    errors.raise_if_any()
    existing,key,fingerprint=creation(Message,"sender_id",current_profile().id,{"exchange_id":exchange.id,"body":body})
    if existing: return jsonify({"message":existing.to_dict()}),201
    message = Message(exchange_id=exchange.id, sender_id=current_profile().id, body=body,
                      creation_key=key,creation_fingerprint=fingerprint)
    db.session.add(message)
    message=commit_creation(message,"sender_id")
    return jsonify({"message": message.to_dict()}), 201


@bp.post("/<exchange_id>/offers")
@require_verified_user
@_transaction
def post_offer(exchange_id: str):
    if _is_service(exchange_id):
        return service.offer(exchange_id)
    exchange = _participant(exchange_id, lock=True)
    _negotiating(exchange)
    body = json_body()
    current = _current_offer(exchange)
    # Pricing evidence is a later Person 2 integration, never client-invented.
    for field in ("price_reference_id", "pricing_range_version"):
        if body.get(field) is not None:
            raise validation_error({field: "price-reference integration is not available yet"})
    old_terms = terms_from_offer(current)
    terms = validate_terms({**old_terms, **{key: body[key] for key in TERM_FIELDS if key in body}}, exchange.mode)
    if same_terms(old_terms, terms):
        db.session.commit()
        return jsonify({"offer": current.to_dict(), "exchange": exchange.to_dict()})
    offer = OfferRevision(
        exchange_id=exchange.id, version=current.version + 1, created_by=current_profile().id,
        **terms, lower_deposit_acknowledged=False,
        owner_accepted_at=None, requester_accepted_at=None,
        price_reference_id=current.price_reference_id, pricing_range_version=current.pricing_range_version,
    )
    db.session.add(offer)
    reset_review(exchange)
    exchange.current_offer_revision = offer.version
    db.session.commit()
    return jsonify({"offer": offer.to_dict(), "exchange": exchange.to_dict()}), 201


@bp.post("/<exchange_id>/accept")
@require_verified_user
@_transaction
def accept_offer(exchange_id: str):
    if _is_service(exchange_id):
        return service.accept(exchange_id)
    exchange = _participant(exchange_id, lock=True)
    body = json_body()
    version = body.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise validation_error({"version": "must be a positive integer"})
    if version != exchange.current_offer_revision:
        raise ApiError(409, "stale_offer", "The offer changed; review the latest revision before accepting")
    offer = _current_offer(exchange)
    if exchange.status == "reserved":
        db.session.commit()
        return jsonify({"exchange": exchange.to_dict(), "current_offer": offer.to_dict()})
    _negotiating(exchange)
    validate_terms(terms_from_offer(offer), exchange.mode, complete=True)
    is_owner = current_profile().id == exchange.owner_id
    if is_owner and offer.uncovered_value_cents:
        if not offer.lower_deposit_acknowledged and body.get("lower_deposit_acknowledged") is not True:
            raise validation_error({
                "lower_deposit_acknowledged": "The lender must explicitly acknowledge the value not covered by the deposit",
            })
        offer.lower_deposit_acknowledged = True
    # A requester cannot set the lender's acknowledgment or the other acceptance.
    field = "owner_accepted_at" if is_owner else "requester_accepted_at"
    if getattr(offer, field) is None:
        setattr(offer, field, utcnow())
    if offer.owner_accepted_at and offer.requester_accepted_at:
        finalize_acceptance(exchange)
    else:
        _available(db.session.get(Listing, exchange.listing_id, populate_existing=True))
    db.session.commit()
    return jsonify({"exchange": exchange.to_dict(), "current_offer": offer.to_dict()})


@bp.post("/<exchange_id>/complete")
@require_verified_user
@_transaction
def complete_service(exchange_id: str):
    if not _is_service(exchange_id):
        _participant(exchange_id)
        raise invalid_transition()
    return service.complete(exchange_id)


@bp.get("/<exchange_id>/evidence")
@require_verified_user
def list_evidence(exchange_id: str):
    service.reject_item_step(exchange_id)
    exchange = _participant(exchange_id)
    evidence = db.session.scalars(
        db.select(Evidence).where(Evidence.exchange_id == exchange.id).order_by(Evidence.created_at)
    ).all()
    return jsonify({"evidence": [photo.to_dict() for photo in evidence]})


@bp.get("/<exchange_id>/evidence/<evidence_id>")
@require_verified_user
def get_evidence_file(exchange_id: str, evidence_id: str):
    service.reject_item_step(exchange_id)
    exchange = _participant(exchange_id)
    authorize_private_read(current_profile().id, exchange.participant_ids)
    evidence = db.session.get(Evidence, evidence_id)
    if evidence is None or evidence.exchange_id != exchange.id:
        raise not_found("evidence")
    response = get_storage().send("private", evidence.private_storage_path, evidence.content_type)
    if request.args.get("preview") == "1":
        # The shared browser API handles JSON. This authenticated representation
        # supplies a small inline preview without adding a public storage URL or
        # changing Person 1's API helper. The default endpoint still serves bytes.
        from .images import private_preview
        response.direct_passthrough = False
        try:
            return jsonify({"data_url": private_preview(response.get_data())})
        finally:
            response.close()
    return response


def _record_return_issue(exchange, body):
    errors = FieldErrors()
    reason = string(body.get("reason"), "reason", errors, required=True, max_len=2000)
    errors.raise_if_any()
    if exchange.mode != "borrow":
        raise invalid_transition()
    if exchange.status == "disputed" and exchange.dispute_reason == reason:
        return
    if exchange.status != "return_pending":
        raise invalid_transition()
    exchange.dispute_reason = reason
    exchange.status = "disputed"
    exchange.updated_at = utcnow()


@bp.post("/<exchange_id>/evidence")
@require_verified_user
@_transaction
def upload_evidence(exchange_id: str):
    service.reject_item_step(exchange_id)
    exchange = _participant(exchange_id, lock=True)
    user_id = current_profile().id
    stage = request.form.get("stage")
    if stage not in (*PICKUP_STAGES, "pre_return", "post_return"):
        raise validation_error({"stage": "must be pre_handoff, handoff, pre_return, or post_return"})
    if stage == "pre_return" and user_id != exchange.requester_id:
        raise forbidden("Only the borrower can upload before-return evidence")
    if stage == "post_return" and user_id != exchange.owner_id:
        raise forbidden("Only the owner can upload after-return evidence")
    expected = "reserved" if stage in PICKUP_STAGES else "on_loan" if stage == "pre_return" else "return_pending"
    if exchange.status != expected or (stage not in PICKUP_STAGES and exchange.mode != "borrow"):
        raise invalid_transition()
    ensure_photos_open(exchange, stage)
    photo = request.files.get("photo")
    if photo is None:
        raise validation_error({"photo": "a photo file is required"})
    from .images import validated_image_stream
    stream = validated_image_stream(photo.stream, current_app.config["MAX_UPLOAD_BYTES"])
    storage = get_storage()
    stored = storage.save("private", stream, current_app.config["MAX_UPLOAD_BYTES"])
    try:
        evidence = Evidence(
            exchange_id=exchange.id, uploader_id=user_id, stage=stage,
            private_storage_path=stored.path, content_type=stored.content_type,
        )
        db.session.add(evidence)
        exchange.updated_at = utcnow()
        db.session.commit()
    except Exception:
        storage.delete("private", stored.path)
        raise
    return jsonify({"evidence": evidence.to_dict()}), 201


@bp.post("/<exchange_id>/handoff")
@require_verified_user
@_transaction
def confirm_handoff(exchange_id: str):
    service.reject_item_step(exchange_id)
    exchange = _participant(exchange_id, lock=True)
    user_id = current_profile().id
    if exchange.status != "reserved":
        if exchange.status in ("on_loan", "return_pending", "completed") and any(
            record["participant_id"] == user_id for record in confirmations_for(exchange, "handoff")
        ):
            db.session.commit()
            return jsonify({"exchange": exchange.to_dict()})
        raise invalid_transition()
    body = json_body()
    if body.get("confirm") is not True or body.get("accept_condition") is not True:
        raise validation_error({"confirm": "confirm must be true", "accept_condition": "accept_condition must be true"})
    photos = require_pickup_photos(exchange)
    acknowledge_and_confirm(photos, user_id)
    if len(confirmations_for(exchange, "handoff")) == 2:
        if exchange.mode == "sale":
            if not mark_listing_sold(db.session, exchange.listing_id, exchange.id):
                raise ApiError(409, "reservation_conflict", "This exchange no longer holds the item reservation")
            exchange.status = "completed"
        else:
            exchange.status = "on_loan"
    exchange.updated_at = utcnow()
    db.session.commit()
    return jsonify({"exchange": exchange.to_dict()})


@bp.post("/<exchange_id>/return")
@require_verified_user
@_transaction
def confirm_return(exchange_id: str):
    service.reject_item_step(exchange_id)
    exchange = _participant(exchange_id, lock=True)
    user_id = current_profile().id
    body = json_body()
    action = body.get("action")
    if exchange.mode != "borrow":
        raise invalid_transition()
    if action not in ("initiate", "accept", "issue"):
        raise validation_error({"action": "must be initiate, accept, or issue"})
    if action == "initiate":
        if user_id != exchange.requester_id:
            raise forbidden("Only the borrower can initiate return")
        if exchange.status not in ("on_loan", "return_pending", "completed"):
            raise invalid_transition()
        require_return_photos(exchange, before_only=True)
        if exchange.status == "on_loan":
            exchange.status = "return_pending"
    elif action == "issue":
        _record_return_issue(exchange, body)
        db.session.commit()
        return jsonify({"exchange": exchange.to_dict()})
    else:
        if exchange.status == "completed" and any(
            record["participant_id"] == user_id for record in confirmations_for(exchange, "return")
        ):
            db.session.commit()
            return jsonify({"exchange": exchange.to_dict()})
        if exchange.status != "return_pending":
            raise invalid_transition()
        photos = require_return_photos(exchange)
        acknowledge_and_confirm(photos, user_id)
        if len(confirmations_for(exchange, "return")) == 2:
            if not release_listing(db.session, exchange.listing_id, exchange.id):
                raise ApiError(409, "reservation_conflict", "This exchange no longer holds the item reservation")
            exchange.status = "completed"
    exchange.updated_at = utcnow()
    db.session.commit()
    return jsonify({"exchange": exchange.to_dict()})


@bp.post("/<exchange_id>/review")
@require_verified_user
@_transaction
def post_review(exchange_id: str):
    exchange = _participant(exchange_id, lock=True)
    if exchange.status != "completed":
        raise ApiError(409, "exchange_not_completed", "Reviews are available only after the exchange is completed")
    user_id = current_profile().id
    if db.session.scalar(db.select(Review).where(Review.exchange_id == exchange.id, Review.reviewer_id == user_id)):
        raise ApiError(409, "already_reviewed", "You already reviewed this exchange")
    body = json_body()
    errors = FieldErrors()
    stars = body.get("stars")
    if isinstance(stars, bool) or not isinstance(stars, int) or not 1 <= stars <= 5:
        errors.add("stars", "must be an integer from 1 to 5")
    answers = body.get("structured_answers")
    if not isinstance(answers, dict):
        errors.add("structured_answers", "must contain all five structured answers")
        answers = {}
    for field in REVIEW_FIELDS:
        if answers.get(field) not in ("yes", "no", "not_applicable"):
            errors.add("structured_answers." + field, "must be yes, no, or not_applicable")
    if exchange.mode == "sale" and answers.get("returned_on_time") != "not_applicable":
        errors.add("structured_answers.returned_on_time", "must be not_applicable for a sale")
    comment = string(body.get("comment"), "comment", errors, max_len=2000)
    errors.raise_if_any()
    review = Review(
        exchange_id=exchange.id, reviewer_id=user_id,
        reviewee_id=exchange.requester_id if user_id == exchange.owner_id else exchange.owner_id,
        stars=stars, structured_answers={field: answers[field] for field in REVIEW_FIELDS}, comment=comment,
    )
    db.session.add(review)
    db.session.commit()
    return jsonify({"review": review.to_dict()}), 201


@bp.post("/<exchange_id>/cancel")
@require_verified_user
@_transaction
def cancel_exchange(exchange_id: str):
    if _is_service(exchange_id):
        return service.cancel(exchange_id)
    exchange = _participant(exchange_id, lock=True)
    errors = FieldErrors()
    reason = string(json_body().get("reason"), "reason", errors, required=True, max_len=2000)
    errors.raise_if_any()
    if exchange.status == "cancelled" and exchange.cancellation_reason == reason:
        db.session.commit()
        return jsonify({"exchange": exchange.to_dict()})
    if exchange.status not in ("negotiating", "reserved") or confirmations_for(exchange, "handoff"):
        raise ApiError(409, "invalid_transition", "Cancellation is available only before either participant confirms pickup")
    if exchange.status == "reserved" and not release_listing(db.session, exchange.listing_id, exchange.id):
        raise ApiError(409, "reservation_conflict", "This exchange no longer holds the item reservation")
    exchange.cancellation_reason = reason
    exchange.status = "cancelled"
    exchange.updated_at = utcnow()
    db.session.commit()
    return jsonify({"exchange": exchange.to_dict()})


@bp.post("/<exchange_id>/dispute")
@require_verified_user
@_transaction
def dispute_exchange(exchange_id: str):
    if _is_service(exchange_id):
        return service.dispute(exchange_id)
    exchange = _participant(exchange_id, lock=True)
    _record_return_issue(exchange, json_body())
    db.session.commit()
    return jsonify({"exchange": exchange.to_dict()})
