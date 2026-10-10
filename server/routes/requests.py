"""Need requests.

    POST  /api/requests/normalize        verified; calls Person 2 normalize_request (stub now)
    GET   /api/requests                  public feed of published requests (sanitized),
                                         or ?mine=1 for the caller's own (full)
    POST  /api/requests                  verified; requester = caller
    GET   /api/requests/{id}             owner: full; others: sanitized only if public
    PATCH /api/requests/{id}             owner only (edit normalized fields)
    GET   /api/requests/{id}/matches     owner only; calls Person 2 match_listings (stub now)
    POST  /api/requests/{id}/publish     owner only; private -> public, draft -> open
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..auth import current_profile, optional_user, require_verified_user
from ..db import db, utcnow
from ..errors import ApiError, forbidden, not_found, validation_error
from ..intelligence import match_listings, normalize_request
from ..models import LISTING_MODES, Listing, NeedRequest
from ..validation import FieldErrors, choice_list, datetime_utc, json_body, json_object, money_cents, string

bp = Blueprint("requests", __name__)


def _load_request(request_id: str) -> NeedRequest:
    need = db.session.get(NeedRequest, request_id)
    if need is None:
        raise not_found("request")
    return need


def _require_requester(need: NeedRequest) -> None:
    if need.requester_id != current_profile().id:
        raise forbidden("Only the requester can modify this request")


def _apply_request_fields(need: NeedRequest, body: dict, *, creating: bool) -> None:
    errors = FieldErrors()

    def present(key: str) -> bool:
        return creating or key in body

    if present("original_text"):
        need.original_text = string(body.get("original_text"), "original_text", errors, required=True, max_len=4000) or ""
    if present("normalized"):
        need.normalized = json_object(body.get("normalized"), "normalized", errors) or {}
    if present("modes"):
        need.modes = choice_list(body.get("modes"), "modes", errors, LISTING_MODES, required=True) or []
    if present("budget_cents"):
        need.budget_cents = money_cents(body.get("budget_cents"), "budget_cents", errors)
    if present("max_deposit_cents"):
        need.max_deposit_cents = money_cents(body.get("max_deposit_cents"), "max_deposit_cents", errors)
    if present("needed_by"):
        need.needed_by = datetime_utc(body.get("needed_by"), "needed_by", errors)
    if present("use_start"):
        need.use_start = datetime_utc(body.get("use_start"), "use_start", errors)
    if present("use_end"):
        need.use_end = datetime_utc(body.get("use_end"), "use_end", errors)
    if present("pickup_windows"):
        windows = body.get("pickup_windows")
        if windows is None:
            windows = []
        if not isinstance(windows, list):
            errors.add("pickup_windows", "must be a list of {start, end}")
        else:
            cleaned = []
            for i, w in enumerate(windows):
                if not isinstance(w, dict):
                    errors.add(f"pickup_windows[{i}]", "must be an object with start and end")
                    continue
                start = datetime_utc(w.get("start"), f"pickup_windows[{i}].start", errors)
                end = datetime_utc(w.get("end"), f"pickup_windows[{i}].end", errors)
                if start and end and end <= start:
                    errors.add(f"pickup_windows[{i}]", "end must be after start")
                if start and end:
                    cleaned.append({"start": start.isoformat().replace("+00:00", "Z"), "end": end.isoformat().replace("+00:00", "Z")})
            need.pickup_windows = cleaned
    if present("area"):
        need.area = string(body.get("area"), "area", errors, max_len=80)

    errors.raise_if_any()

    cross = FieldErrors()
    if need.use_start and need.use_end and need.use_end <= need.use_start:
        cross.add("use_end", "must be after use_start")
    cross.raise_if_any()


@bp.post("/api/requests/normalize")
@require_verified_user
def normalize():
    body = json_body()
    errors = FieldErrors()
    text = string(body.get("text"), "text", errors, required=True, max_len=4000)
    errors.raise_if_any()
    result = normalize_request(text, utcnow(), current_app.config["DISPLAY_TIMEZONE"])
    return jsonify({"normalized": result, "fixture": result.get("source") == "stub"})


@bp.get("/api/requests")
@optional_user
def list_requests():
    me = current_profile()
    if request.args.get("mine") in ("1", "true"):
        if me is None:
            raise ApiError(401, "auth_required", "Sign in to see your requests")
        rows = db.session.scalars(
            db.select(NeedRequest).where(NeedRequest.requester_id == me.id).order_by(NeedRequest.created_at.desc())
        ).all()
        return jsonify({"requests": [r.to_owner_dict() for r in rows], "view": "owner"})
    rows = db.session.scalars(
        db.select(NeedRequest)
        .where(NeedRequest.visibility == "public", NeedRequest.status == "open")
        .order_by(NeedRequest.created_at.desc())
        .limit(200)
    ).all()
    return jsonify({"requests": [r.to_public_dict() for r in rows], "view": "public"})


@bp.post("/api/requests")
@require_verified_user
def create_request():
    body = json_body()
    need = NeedRequest(requester_id=current_profile().id, visibility="private", status="draft")
    _apply_request_fields(need, body, creating=True)
    db.session.add(need)
    db.session.commit()
    return jsonify({"request": need.to_owner_dict(), "view": "owner"}), 201


@bp.get("/api/requests/<request_id>")
@optional_user
def get_request(request_id: str):
    need = _load_request(request_id)
    me = current_profile()
    if me is not None and need.requester_id == me.id:
        return jsonify({"request": need.to_owner_dict(), "view": "owner"})
    if need.visibility == "public" and need.status == "open":
        return jsonify({"request": need.to_public_dict(), "view": "public"})
    raise not_found("request")  # do not reveal private requests exist


@bp.patch("/api/requests/<request_id>")
@require_verified_user
def update_request(request_id: str):
    need = _load_request(request_id)
    _require_requester(need)
    if need.status in ("fulfilled", "cancelled", "expired"):
        raise ApiError(409, "request_closed", f"A {need.status} request cannot be edited")
    body = json_body()
    _apply_request_fields(need, body, creating=False)
    if "status" in body:
        if body["status"] != "cancelled":
            raise validation_error({"status": "requester may only set 'cancelled' here"})
        need.status = "cancelled"
    db.session.commit()
    return jsonify({"request": need.to_owner_dict(), "view": "owner"})


@bp.get("/api/requests/<request_id>/matches")
@require_verified_user
def get_matches(request_id: str):
    need = _load_request(request_id)
    _require_requester(need)
    candidates = db.session.scalars(
        db.select(Listing)
        .where(Listing.status == "available", Listing.owner_id != need.requester_id)
        .order_by(Listing.created_at.desc())
        .limit(200)
    ).all()
    by_id = {l.id: l for l in candidates}
    result = match_listings(need.to_owner_dict(), [l.to_dict() for l in candidates])

    def hydrate(entries):
        out = []
        for entry in entries:
            listing = by_id.get(entry.get("listing_id"))
            if listing is None:
                continue  # never return a listing that is not a real current row
            out.append({**entry, "listing": listing.to_dict()})
        return out

    return jsonify(
        {
            "request_id": need.id,
            "source": result.get("source", "unknown"),
            "fixture": result.get("source") == "stub",
            "confirmed": hydrate(result.get("confirmed", [])),
            "needs_confirmation": hydrate(result.get("needs_confirmation", [])),
            "rejected": hydrate(result.get("rejected", [])),
        }
    )


@bp.post("/api/requests/<request_id>/publish")
@require_verified_user
def publish_request(request_id: str):
    need = _load_request(request_id)
    _require_requester(need)
    if need.status in ("fulfilled", "cancelled", "expired"):
        raise ApiError(409, "request_closed", f"A {need.status} request cannot be published")
    need.visibility = "public"
    need.status = "open"
    db.session.commit()
    return jsonify({"request": need.to_owner_dict(), "public_preview": need.to_public_dict(), "view": "owner"})
