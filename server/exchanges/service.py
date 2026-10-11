"""Service-only exchange workflow; item exchange routes keep their existing path."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import jsonify

from ..auth import current_profile
from ..idempotency import creation, commit_creation
from ..db import db, utcnow
from ..errors import ApiError, forbidden, not_found, validation_error
from ..models import Exchange, Listing, Message, NeedRequest, OfferRevision, MeetingSpot, Profile
from ..reservation import release_listing, reserve_listing
from ..validation import FieldErrors, datetime_utc, json_body, money_cents, string


_ITEM_TERMS = ("sale_price_cents", "rental_fee_cents", "agreed_item_value_cents",
               "deposit_cents", "collateral_percent", "lower_deposit_acknowledged",
               "proposed_item_value_cents", "meeting_spot_id", "meeting_spot_ids", "pickup_windows", "return_windows",
               "condition", "condition_snapshot", "evidence", "evidence_ids",
               "handoff", "pickup", "return",
               "pickup_meeting_spot_id", "pickup_at", "return_meeting_spot_id",
               "return_deadline", "pricing_range_version", "price_reference_id")


def load_service(exchange_id: str) -> Exchange | None:
    exchange = db.session.get(Exchange, exchange_id)
    if exchange is None or exchange.mode != "service":
        return None
    if current_profile().id not in exchange.participant_ids:
        raise forbidden("Only participants can access this exchange")
    return exchange


def _require_service(exchange_id: str) -> Exchange:
    exchange = load_service(exchange_id)
    if exchange is None:
        raise not_found("exchange")
    return exchange


def _lock_service(exchange_id: str) -> Exchange:
    exchange = _require_service(exchange_id)
    db.session.execute(db.update(Exchange).where(Exchange.id == exchange_id).values(updated_at=Exchange.updated_at))
    db.session.refresh(exchange)
    return exchange


def _current_offer(exchange: Exchange) -> OfferRevision | None:
    return next((offer for offer in exchange.offers if offer.version == exchange.current_offer_revision), None)


def _fits_window(listing: Listing, scheduled_at: datetime, duration: int) -> bool:
    if scheduled_at.tzinfo is None:  # SQLite returns stored UTC timestamps without tzinfo.
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    end_at = scheduled_at + timedelta(minutes=duration)
    try:
        for window in listing.service_available_windows or []:
            start = datetime.fromisoformat(window["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(window["end"].replace("Z", "+00:00"))
            if start.utcoffset() is not None and end.utcoffset() is not None and start <= scheduled_at and end_at <= end:
                return True
    except (KeyError, TypeError, ValueError, AttributeError):
        return False
    return False


def _detail(exchange: Exchange) -> dict:
    offer = _current_offer(exchange)
    return {"fixture": False, "exchange": exchange.to_dict(),
            "current_offer": offer.to_dict() if offer else None,
            "offers": [row.to_dict() for row in exchange.offers],
            "listing": db.session.get(Listing,exchange.listing_id).to_dict(),
            "participants": [db.session.get(Profile,p).to_public_dict() for p in exchange.participant_ids]}


def list_for_caller():
    profile_id = current_profile().id
    rows = db.session.scalars(db.select(Exchange).where(
        Exchange.mode == "service",
        (Exchange.owner_id == profile_id) | (Exchange.requester_id == profile_id),
    ).order_by(Exchange.created_at.desc())).all()
    return jsonify({"fixture": False, "exchanges": [row.to_dict() for row in rows]})


def create():
    body = json_body()
    existing,key,fingerprint=creation(Exchange,"requester_id",current_profile().id,body)
    if existing: return jsonify({"exchange":existing.to_dict(),"current_offer":_current_offer(existing).to_dict() if _current_offer(existing) else None}),201
    if body.get("mode") != "service":
        raise validation_error({"mode": "must be service"})
    for field in _ITEM_TERMS:
        if field in body:
            raise validation_error({field: "not applicable to services"})
    errors = FieldErrors()
    listing_id = string(body.get("listing_id"), "listing_id", errors, required=True, max_len=32)
    source_id = string(body.get("source_request_id"), "source_request_id", errors, max_len=32)
    errors.raise_if_any()
    listing = db.session.get(Listing, listing_id)
    if listing is None:
        raise not_found("listing")
    if "service" not in (listing.allowed_modes or []) or listing.status != "available":
        raise ApiError(409, "listing_unavailable", "Service listing is unavailable")
    requester_id = current_profile().id
    if requester_id == listing.owner_id:
        raise forbidden("Cannot request your own service")
    if source_id:
        need = db.session.get(NeedRequest, source_id)
        if need is None or need.requester_id != requester_id or "service" not in (need.modes or []):
            raise validation_error({"source_request_id": "must be your service request"})
        if need.status not in ("draft", "open"):
            raise ApiError(409, "request_closed", "This request is closed")
    exchange = Exchange(listing_id=listing.id, owner_id=listing.owner_id,
                        requester_id=requester_id, source_request_id=source_id,
                        mode="service", status="negotiating",creation_key=key,creation_fingerprint=fingerprint)
    db.session.add(exchange)
    exchange=commit_creation(exchange,"requester_id")
    return jsonify({"exchange": exchange.to_dict(), "current_offer": None}), 201


def detail(exchange_id: str):
    return jsonify(_detail(_require_service(exchange_id)))


def messages(exchange_id: str):
    _require_service(exchange_id)
    rows = db.session.scalars(db.select(Message).where(Message.exchange_id == exchange_id)
                              .order_by(Message.created_at, Message.id)).all()
    return jsonify({"fixture": False, "messages": [row.to_dict() for row in rows]})


def post_message(exchange_id: str):
    exchange = _require_service(exchange_id)
    if exchange.status in ("cancelled", "completed"):
        raise ApiError(409, "invalid_transition", "This service conversation is closed")
    body = json_body()
    errors = FieldErrors()
    message = string(body.get("body"), "body", errors, required=True, max_len=4000)
    errors.raise_if_any()
    existing,key,fingerprint=creation(Message,"sender_id",current_profile().id,{"exchange_id":exchange.id,"body":message})
    if existing: return jsonify({"message":existing.to_dict()}),201
    row = Message(exchange_id=exchange.id, sender_id=current_profile().id, body=message,
                  creation_key=key,creation_fingerprint=fingerprint)
    db.session.add(row)
    row=commit_creation(row,"sender_id")
    return jsonify({"message": row.to_dict()}), 201


def offer(exchange_id: str):
    exchange = _lock_service(exchange_id)
    if exchange.status != "negotiating":
        raise ApiError(409, "invalid_transition", "Only negotiating services can receive offers")
    body = json_body()
    errors = FieldErrors()
    for field in _ITEM_TERMS:
        if field in body:
            errors.add(field, "not applicable to services")
    price = money_cents(body.get("service_price_cents"), "service_price_cents", errors, required=True)
    duration = body.get("service_duration_minutes")
    if isinstance(duration, bool) or not isinstance(duration, int) or not 1 <= duration <= 1440:
        errors.add("service_duration_minutes", "must be an integer from 1 to 1440")
    scheduled_at = datetime_utc(body.get("service_scheduled_at"), "service_scheduled_at", errors)
    if scheduled_at is None and body.get("service_scheduled_at") is None:
        errors.add("service_scheduled_at", "required")
    delivery = body.get("service_delivery", "remote")
    spot_id = body.get("service_meeting_spot_id")
    if delivery not in ("remote", "in_person"):
        errors.add("service_delivery", "must be remote or in_person")
    if delivery == "in_person":
        spot = db.session.get(MeetingSpot, spot_id) if isinstance(spot_id,str) else None
        if spot is None or not spot.is_active:
            errors.add("service_meeting_spot_id", "choose an active catalog meeting spot")
    elif spot_id is not None:
        errors.add("service_meeting_spot_id", "not used for remote services")
    errors.raise_if_any()
    listing = db.session.get(Listing, exchange.listing_id)
    if not _fits_window(listing, scheduled_at, duration):
        raise validation_error({"service_scheduled_at": "must fit an available time window"})
    version = exchange.current_offer_revision + 1
    row = OfferRevision(exchange=exchange, version=version, created_by=current_profile().id,
                        service_price_cents=price, service_duration_minutes=duration,
                        service_scheduled_at=scheduled_at,service_delivery=delivery,service_meeting_spot_id=spot_id)
    exchange.current_offer_revision = version
    db.session.add(row)
    db.session.commit()
    return jsonify({"offer": row.to_dict(), "exchange": exchange.to_dict()}), 201


def accept(exchange_id: str):
    exchange = _lock_service(exchange_id)
    body = json_body()
    for field in _ITEM_TERMS:
        if field in body:
            raise validation_error({field: "not applicable to services"})
    version = body.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise validation_error({"version": "must be the current offer version"})
    row = _current_offer(exchange)
    if row is None or version != exchange.current_offer_revision:
        raise ApiError(409, "stale_offer", "Accept the current offer revision")
    if exchange.status not in ("negotiating", "scheduled"):
        raise ApiError(409, "invalid_transition", "Service cannot be accepted in this state")
    listing = db.session.get(Listing, exchange.listing_id)
    if not _fits_window(listing, row.service_scheduled_at, row.service_duration_minutes):
        raise ApiError(409, "schedule_unavailable", "Service availability changed; propose a new time")
    if row.service_delivery == "in_person":
        spot = db.session.get(MeetingSpot, row.service_meeting_spot_id)
        if spot is None or not spot.is_active:
            raise validation_error({"service_meeting_spot_id":"choose an active catalog spot"})
    field = "owner_accepted_at" if current_profile().id == exchange.owner_id else "requester_accepted_at"
    if getattr(row, field) is None:
        setattr(row, field, utcnow())
    if row.owner_accepted_at and row.requester_accepted_at and exchange.status == "negotiating":
        if not reserve_listing(db.session, exchange.listing_id, exchange.id):
            db.session.rollback()
            raise ApiError(409, "reservation_conflict", "Service listing is already reserved")
        exchange.status = "scheduled"
    db.session.commit()
    return jsonify({"exchange": exchange.to_dict(), "current_offer": row.to_dict()})


def complete(exchange_id: str):
    exchange = _lock_service(exchange_id)
    if exchange.status not in ("scheduled", "completed"):
        raise ApiError(409, "invalid_transition", "Only a scheduled service can be completed")
    body = json_body()
    if body.get("confirm") is not True:
        raise validation_error({"confirm": "must be true after the service happened"})
    field = ("owner_service_confirmed_at" if current_profile().id == exchange.owner_id
             else "requester_service_confirmed_at")
    if getattr(exchange, field) is None:
        setattr(exchange, field, utcnow())
    if exchange.owner_service_confirmed_at and exchange.requester_service_confirmed_at:
        release_listing(db.session, exchange.listing_id, exchange.id)
        exchange.status = "completed"
    db.session.commit()
    return jsonify({"exchange": exchange.to_dict()})


def cancel(exchange_id: str):
    exchange = _lock_service(exchange_id)
    if exchange.status not in ("negotiating", "scheduled"):
        raise ApiError(409, "invalid_transition", "Service cannot be cancelled in this state")
    body = json_body()
    errors = FieldErrors()
    reason = string(body.get("reason"), "reason", errors, required=True, max_len=1000)
    errors.raise_if_any()
    if exchange.status == "scheduled":
        release_listing(db.session, exchange.listing_id, exchange.id)
    exchange.status = "cancelled"
    exchange.cancellation_reason = reason
    db.session.commit()
    return jsonify({"exchange": exchange.to_dict()})


def dispute(exchange_id: str):
    exchange = _lock_service(exchange_id)
    if exchange.status not in ("scheduled", "completed"):
        raise ApiError(409, "invalid_transition", "Service cannot be disputed in this state")
    body = json_body()
    errors = FieldErrors()
    reason = string(body.get("reason"), "reason", errors, required=True, max_len=1000)
    errors.raise_if_any()
    if exchange.status == "scheduled":
        release_listing(db.session, exchange.listing_id, exchange.id)
    exchange.status = "disputed"
    exchange.dispute_reason = reason
    db.session.commit()
    return jsonify({"exchange": exchange.to_dict()})


def reject_item_step(exchange_id: str) -> None:
    if load_service(exchange_id) is not None:
        raise ApiError(409, "invalid_transition", "Services have no handoff, evidence, or return step")
