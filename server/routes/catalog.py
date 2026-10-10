"""Listings, listing photos, meeting spots, and public media.

    GET    /api/listings                 public, filterable
    POST   /api/listings                 verified user; owner = caller
    GET    /api/listings/{id}            public
    PATCH  /api/listings/{id}            owner only
    POST   /api/listings/{id}/photo      owner only, multipart "photo"
    GET    /api/meeting-spots            public
    GET    /media/public/<path>          public listing photos (local backend)
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..auth import current_profile, require_verified_user
from ..db import db
from ..errors import ApiError, forbidden, not_found, validation_error
from ..models import LISTING_MODES, LISTING_STATUSES, Listing, MeetingSpot
from ..storage import get_storage
from ..validation import (
    FieldErrors,
    choice_list,
    json_body,
    json_object,
    money_cents,
    percent,
    string,
    string_list,
)

bp = Blueprint("catalog", __name__)

_CONDITIONS = ("new", "like_new", "good", "fair", "worn")


def _load_listing(listing_id: str) -> Listing:
    listing = db.session.get(Listing, listing_id)
    if listing is None:
        raise not_found("listing")
    return listing


def _require_owner(listing: Listing) -> None:
    if listing.owner_id != current_profile().id:
        raise forbidden("Only the listing owner can modify this listing")


def _apply_listing_fields(listing: Listing, body: dict, *, creating: bool) -> None:
    """Validate and copy editable fields. Ignores owner_id/status/id from the client."""
    errors = FieldErrors()

    def present(key: str) -> bool:
        return creating or key in body

    if present("title"):
        listing.title = string(body.get("title"), "title", errors, required=True, max_len=120) or ""
    if present("category"):
        listing.category = string(body.get("category"), "category", errors, required=True, max_len=60) or ""
    if present("description"):
        listing.description = string(body.get("description"), "description", errors, max_len=4000)
    if present("specifications"):
        listing.specifications = json_object(body.get("specifications"), "specifications", errors) or {}
    if present("condition"):
        cond = string(body.get("condition"), "condition", errors, max_len=40)
        if cond is not None and cond not in _CONDITIONS:
            errors.add("condition", f"must be one of: {', '.join(_CONDITIONS)}")
        listing.condition = cond
    if present("accessories"):
        listing.accessories = string_list(body.get("accessories"), "accessories", errors) or []
    if present("known_defects"):
        listing.known_defects = string_list(body.get("known_defects"), "known_defects", errors) or []
    if present("allowed_modes"):
        listing.allowed_modes = (
            choice_list(body.get("allowed_modes"), "allowed_modes", errors, LISTING_MODES, required=True) or []
        )
    if present("sale_price_cents"):
        listing.sale_price_cents = money_cents(body.get("sale_price_cents"), "sale_price_cents", errors)
    if present("rental_fee_cents"):
        listing.rental_fee_cents = money_cents(body.get("rental_fee_cents"), "rental_fee_cents", errors)
    if present("proposed_item_value_cents"):
        listing.proposed_item_value_cents = money_cents(
            body.get("proposed_item_value_cents"), "proposed_item_value_cents", errors
        )
    if present("collateral_percent"):
        listing.collateral_percent = percent(body.get("collateral_percent"), "collateral_percent", errors)
    if present("availability"):
        listing.availability = json_object(body.get("availability"), "availability", errors) or {}
    if present("meeting_spot_ids"):
        ids = string_list(body.get("meeting_spot_ids"), "meeting_spot_ids", errors) or []
        if ids:
            known = set(db.session.scalars(db.select(MeetingSpot.id).where(MeetingSpot.id.in_(ids))))
            missing = [i for i in ids if i not in known]
            if missing:
                errors.add("meeting_spot_ids", f"unknown meeting spots: {', '.join(missing)}")
        listing.meeting_spot_ids = ids

    errors.raise_if_any()

    # Cross-field rules: a mode needs its price fields; loans default to 100% collateral.
    cross = FieldErrors()
    modes = listing.allowed_modes or []
    if "sale" in modes and listing.sale_price_cents is None:
        cross.add("sale_price_cents", "required when 'sale' is an allowed mode")
    if "borrow" in modes:
        if listing.proposed_item_value_cents is None:
            cross.add("proposed_item_value_cents", "required when 'borrow' is an allowed mode")
        if listing.rental_fee_cents is None:
            listing.rental_fee_cents = 0  # free loan is explicit, not unknown
        if listing.collateral_percent is None:
            listing.collateral_percent = 100
    cross.raise_if_any()


@bp.get("/api/listings")
def list_listings():
    query = db.select(Listing)
    status = request.args.get("status", "available")
    if status != "all":
        if status not in LISTING_STATUSES:
            raise validation_error({"status": f"must be one of: {', '.join(LISTING_STATUSES)}, all"})
        query = query.where(Listing.status == status)
    category = request.args.get("category")
    if category:
        query = query.where(Listing.category == category)
    owner_id = request.args.get("owner_id")
    if owner_id:
        query = query.where(Listing.owner_id == owner_id)
    mode = request.args.get("mode")
    if mode and mode not in LISTING_MODES:
        raise validation_error({"mode": f"must be one of: {', '.join(LISTING_MODES)}"})
    listings = db.session.scalars(query.order_by(Listing.created_at.desc()).limit(200)).all()
    if mode:
        listings = [l for l in listings if mode in (l.allowed_modes or [])]
    return jsonify({"listings": [l.to_dict() for l in listings]})


@bp.post("/api/listings")
@require_verified_user
def create_listing():
    body = json_body()
    listing = Listing(owner_id=current_profile().id, status="available")
    _apply_listing_fields(listing, body, creating=True)
    db.session.add(listing)
    db.session.commit()
    return jsonify({"listing": listing.to_dict()}), 201


@bp.get("/api/listings/<listing_id>")
def get_listing(listing_id: str):
    return jsonify({"listing": _load_listing(listing_id).to_dict()})


@bp.patch("/api/listings/<listing_id>")
@require_verified_user
def update_listing(listing_id: str):
    listing = _load_listing(listing_id)
    _require_owner(listing)
    if listing.status in ("reserved", "sold"):
        raise ApiError(409, "listing_locked", f"A {listing.status} listing cannot be edited")
    body = json_body()
    _apply_listing_fields(listing, body, creating=False)
    if "status" in body:
        if body["status"] not in ("available", "withdrawn"):
            raise validation_error({"status": "owner may only set 'available' or 'withdrawn'"})
        listing.status = body["status"]
    db.session.commit()
    return jsonify({"listing": listing.to_dict()})


@bp.post("/api/listings/<listing_id>/photo")
@require_verified_user
def upload_listing_photo(listing_id: str):
    listing = _load_listing(listing_id)
    _require_owner(listing)
    upload = request.files.get("photo")
    if upload is None:
        raise validation_error({"photo": "multipart field 'photo' is required"})
    storage = get_storage()
    stored = storage.save("public", upload.stream, current_app.config["MAX_UPLOAD_BYTES"])
    old = listing.public_photo_path
    listing.public_photo_path = stored.path
    db.session.commit()
    if old:
        storage.delete("public", old)
    return jsonify({"listing": listing.to_dict()})


@bp.get("/media/public/<path:path>")
def public_media(path: str):
    return get_storage().send("public", path)


@bp.get("/api/meeting-spots")
def list_meeting_spots():
    spots = db.session.scalars(
        db.select(MeetingSpot).where(MeetingSpot.is_active.is_(True)).order_by(MeetingSpot.label)
    ).all()
    return jsonify({"meeting_spots": [s.to_dict() for s in spots]})
