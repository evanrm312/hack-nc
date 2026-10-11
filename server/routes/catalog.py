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

from datetime import datetime, timedelta

from sqlalchemy import cast, String
from ..exchanges.images import validated_image_stream

from flask import Blueprint, current_app, jsonify, request

from ..auth import current_profile, require_verified_user
from ..community import listing_visibility, require_listing_access, membership
from ..idempotency import creation, commit_creation
from ..db import db
from ..errors import ApiError, forbidden, not_found, validation_error
from ..models import LISTING_MODES, LISTING_STATUSES, SERVICE_CATEGORIES, Listing, MeetingSpot
from ..storage import get_storage, authorize_private_read
from ..validation import (
    FieldErrors,
    choice_list,
    json_body,
    json_object,
    money_cents,
    percent,
    string,
    string_list,
    time_windows,
)

bp = Blueprint("catalog", __name__)

_CONDITIONS = ("new", "like_new", "good", "fair", "worn")


def _load_listing(listing_id: str) -> Listing:
    listing = db.session.get(Listing, listing_id)
    require_listing_access(listing, current_profile())
    if listing is None or (listing.status == "draft" and (current_profile() is None or listing.owner_id != current_profile().id)):
        raise not_found("listing")
    return listing


def _require_owner(listing: Listing) -> None:
    if listing.owner_id != current_profile().id:
        raise forbidden("Only the listing owner can modify this listing")


def _lock_listing_for_edit(listing):
    result = db.session.execute(db.update(Listing).where(Listing.id == listing.id,
        Listing.owner_id == current_profile().id, Listing.status.notin_(("reserved", "sold")))
        .values(updated_at=Listing.updated_at))
    db.session.refresh(listing)
    if result.rowcount != 1:
        raise ApiError(409,"listing_locked",f"A {listing.status} listing cannot be edited")


def _apply_listing_fields(listing: Listing, body: dict, *, creating: bool) -> None:
    """Validate and copy editable fields. Ignores owner_id/status/id from the client."""
    errors = FieldErrors()

    def present(key: str) -> bool:
        return creating or key in body

    if present("audience") or present("club_id"):
        audience = body.get("audience", "public" if creating else listing.audience)
        club_id = body.get("club_id", None if creating else listing.club_id)
        if audience not in ("public", "club"):
            errors.add("audience", "must be public or club")
        elif audience == "public" and club_id is not None:
            errors.add("club_id", "must be null for public listings")
        elif audience == "club":
            viewer = current_profile()
            if not isinstance(club_id, str) or not membership(club_id, viewer.id if viewer else None):
                errors.add("club_id", "choose one of your clubs")
            elif not creating and (listing.club_id != club_id or listing.audience != audience):
                errors.add("audience", "audience cannot change after creation")
        if not creating and (listing.audience != audience or listing.club_id != club_id):
            errors.add("audience", "audience cannot change after creation")
        listing.audience = audience
        listing.club_id = club_id
    if present("title"):
        listing.title = string(body.get("title"), "title", errors, required=True, max_len=120) or ""
    if present("category"):
        listing.category = string(body.get("category"), "category", errors, required=True, max_len=60) or ""
    if present("description"):
        listing.description = string(body.get("description"), "description", errors, max_len=4000)
    modes = (choice_list(body.get("allowed_modes"), "allowed_modes", errors,
                         LISTING_MODES, required=True) if present("allowed_modes")
             else listing.allowed_modes)
    if "service" in (modes or []):
        if modes != ["service"]:
            errors.add("allowed_modes", "service cannot be combined with sale or borrow")
        if not creating and "service" not in (listing.allowed_modes or []):
            errors.add("allowed_modes", "listing kind cannot be changed")
        if listing.category not in SERVICE_CATEGORIES:
            errors.add("category", f"must be one of: {', '.join(SERVICE_CATEGORIES)}")
        if not listing.description:
            errors.add("description", "required for a service")
        for field in ("specifications", "condition", "accessories", "known_defects",
                      "sale_price_cents", "rental_fee_cents", "proposed_item_value_cents",
                      "agreed_item_value_cents", "deposit_cents", "collateral_percent",
                      "condition_snapshot", "availability", "meeting_spot_ids"):
            if field in body:
                errors.add(field, "not applicable to services")
        if present("service_price_cents"):
            listing.service_price_cents = money_cents(body.get("service_price_cents"),
                                                       "service_price_cents", errors, required=True)
        if present("service_duration_minutes"):
            duration = body.get("service_duration_minutes")
            if isinstance(duration, bool) or not isinstance(duration, int) or not 1 <= duration <= 1440:
                errors.add("service_duration_minutes", "must be an integer from 1 to 1440")
            else:
                listing.service_duration_minutes = duration
        if present("service_available_windows"):
            listing.service_available_windows = time_windows(
                body.get("service_available_windows"), "service_available_windows", errors,
                required=True)
        if (listing.service_duration_minutes and listing.service_available_windows
                and not any(
                    datetime.fromisoformat(window["start"].replace("Z", "+00:00"))
                    + timedelta(minutes=listing.service_duration_minutes)
                    <= datetime.fromisoformat(window["end"].replace("Z", "+00:00"))
                    for window in listing.service_available_windows
                )):
            errors.add("service_available_windows", "at least one window must fit the duration")
        listing.allowed_modes = ["service"]
        errors.raise_if_any()
        return
    if "service" in (listing.allowed_modes or []):
        errors.add("allowed_modes", "listing kind cannot be changed")
    for field in ("service_price_cents", "service_duration_minutes", "service_available_windows"):
        if field in body and body[field] not in (None, []):
            errors.add(field, "only allowed for services")
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
        listing.allowed_modes = modes or []
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
    viewer = current_profile() if request.headers.get("Authorization") else None
    query = query.where(listing_visibility(viewer))
    query = query.where(db.or_(Listing.status != "draft", Listing.owner_id == viewer.id) if viewer else Listing.status != "draft")
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
    if mode:
        # Modes are a server-validated finite string vocabulary. Apply before limit.
        query = query.where(cast(Listing.allowed_modes, String).like(f'%"{mode}"%'))
    listings = db.session.scalars(query.order_by(Listing.created_at.desc()).limit(200)).all()
    response = jsonify({"listings": [l.to_dict() for l in listings]})
    if any(l.status == "draft" for l in listings):
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.post("/api/listings")
@require_verified_user
def create_listing():
    body = json_body()
    existing,key,fingerprint=creation(Listing,"owner_id",current_profile().id,body)
    if existing:
        require_listing_access(existing, current_profile())
        return jsonify({"listing":existing.to_dict()}),201
    listing = Listing(owner_id=current_profile().id, status="draft", publication_required=True,
                      creation_key=key,creation_fingerprint=fingerprint)
    _apply_listing_fields(listing, body, creating=True)
    db.session.add(listing)
    listing=commit_creation(listing,"owner_id")
    return jsonify({"listing": listing.to_dict()}), 201


@bp.get("/api/listings/<listing_id>")
def get_listing(listing_id: str):
    listing = _load_listing(listing_id)
    response = jsonify({"listing": listing.to_dict()})
    if listing.status == "draft":
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.patch("/api/listings/<listing_id>")
@require_verified_user
def update_listing(listing_id: str):
    listing = _load_listing(listing_id)
    _require_owner(listing)
    _lock_listing_for_edit(listing)
    if listing.status in ("reserved", "sold"):
        raise ApiError(409, "listing_locked", f"A {listing.status} listing cannot be edited")
    body = json_body()
    _apply_listing_fields(listing, body, creating=False)
    if listing.publication_required and listing.status != "draft" and not listing.description:
        raise validation_error({"description":"required for published listings"})
    if "status" in body:
        if listing.status == "draft":
            raise validation_error({"status":"a draft stays private until photo publication"})
        if body["status"] not in ("available", "withdrawn"):
            raise validation_error({"status": "owner may only set 'available' or 'withdrawn'"})
        if body["status"] == "available" and listing.publication_required and (listing.status == "draft" or not listing.public_photo_path):
            raise validation_error({"status": "use the photo publication endpoint"})
        listing.status = body["status"]
    db.session.commit()
    return jsonify({"listing": listing.to_dict()})


@bp.post("/api/listings/<listing_id>/photo")
@require_verified_user
def upload_listing_photo(listing_id: str):
    listing = _load_listing(listing_id)
    _require_owner(listing)
    _lock_listing_for_edit(listing)
    if listing.status in ("reserved", "sold", "draft"):
        raise ApiError(409, "listing_locked", "Use publication for drafts; reserved or sold photos cannot change")
    upload = request.files.get("photo")
    if upload is None:
        raise validation_error({"photo": "multipart field 'photo' is required"})
    storage = get_storage()
    scope = "private" if listing.club_id else "public"
    stored = storage.save(scope, validated_image_stream(upload.stream, min(current_app.config["MAX_UPLOAD_BYTES"], 5 * 1024 * 1024)), current_app.config["MAX_UPLOAD_BYTES"])
    old = listing.public_photo_path
    listing.public_photo_path = stored.path
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        storage.delete(scope, stored.path)
        raise
    if old:
        storage.delete(scope, old)
    return jsonify({"listing": listing.to_dict()})


@bp.get("/media/public/<path:path>")
def public_media(path: str):
    rows = db.session.scalars(db.select(Listing).where(Listing.public_photo_path == path)).all()
    restricted = [row for row in rows if row.club_id]
    if restricted:
        viewer = current_profile()
        visible = next((row for row in restricted if membership(row.club_id, viewer.id if viewer else None)), None)
        if visible is None:
            raise not_found("photo")
        authorize_private_read(viewer.id, {viewer.id})
        if request.args.get("preview") == "1":
            from ..exchanges.images import private_preview
            data = get_storage().send("private", path)
            data.direct_passthrough = False
            return jsonify({"data_url": private_preview(data.get_data())})
        return get_storage().send("private", path)
    return get_storage().send("public", path)


@bp.get("/api/meeting-spots")
def list_meeting_spots():
    spots = db.session.scalars(
        db.select(MeetingSpot).where(MeetingSpot.is_active.is_(True)).order_by(MeetingSpot.label)
    ).all()
    return jsonify({"meeting_spots": [s.to_dict() for s in spots]})


@bp.post("/api/listings/<listing_id>/publish")
@require_verified_user
def publish_listing(listing_id):
    # Serialize retries and prevent two uploads publishing the same draft.
    db.session.execute(db.update(Listing).where(Listing.id == listing_id,
        Listing.owner_id == current_profile().id).values(updated_at=Listing.updated_at))
    listing = _load_listing(listing_id)
    db.session.refresh(listing)
    _require_owner(listing)
    if listing.status == "available" and listing.publication_required and listing.public_photo_path:
        db.session.rollback()
        return jsonify({"listing": listing.to_dict()})
    if listing.status != "draft":
        raise ApiError(409, "listing_locked", "Only a draft can be published")
    # Revalidate persisted terms rather than trusting the client or a status PATCH.
    body = listing.to_dict()
    editable = {k: v for k, v in body.items() if k not in
        ("id", "owner_id", "owner", "club", "status", "active_exchange_id", "public_photo_url", "created_at", "updated_at")}
    _apply_listing_fields(listing, editable, creating=True)
    if not listing.description or not listing.description.strip():
        raise validation_error({"description": "required for publication"})
    upload = request.files.get("photo")
    if upload is None:
        raise validation_error({"photo": "an image is required for publication"})
    limit = min(current_app.config["MAX_UPLOAD_BYTES"], 5 * 1024 * 1024)
    stream = validated_image_stream(upload.stream, limit)
    storage = get_storage()
    scope = "private" if listing.club_id else "public"
    stored = storage.save(scope, stream, limit)
    try:
        listing.public_photo_path = stored.path
        listing.status = "available"
        db.session.commit()
    except Exception:
        db.session.rollback()
        storage.delete(scope, stored.path)
        raise
    return jsonify({"listing": listing.to_dict()})


@bp.after_request
def private_owner_responses(response):
    if request.headers.get("Authorization"):
        response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
