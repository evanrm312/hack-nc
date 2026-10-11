"""GET/PATCH /api/me"""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..auth import current_profile, require_verified_user
from ..db import db
from ..models import MeetingSpot
from ..validation import FieldErrors, json_body, string

bp = Blueprint("me", __name__)


@bp.get("/api/me")
@require_verified_user
def get_me():
    return jsonify({"profile": current_profile().to_me_dict()})


@bp.patch("/api/me")
@require_verified_user
def update_me():
    body = json_body()
    errors = FieldErrors()
    profile = current_profile()
    display_name = string(body.get("display_name", profile.display_name), "display_name", errors, required=True, max_len=80)
    if "preferred_meeting_spot_id" in body:
        spot_id = string(body["preferred_meeting_spot_id"], "preferred_meeting_spot_id", errors, max_len=32)
        spot = db.session.get(MeetingSpot, spot_id) if spot_id else None
        if spot_id and (spot is None or not spot.is_active):
            errors.add("preferred_meeting_spot_id", "choose an active catalog spot")
        profile.preferred_meeting_spot_id = spot_id
    if "bio" in body:
        profile.bio = string(body["bio"], "bio", errors, max_len=300)
    if "graduation_year" in body:
        year = body["graduation_year"]
        if year is not None and (isinstance(year, bool) or not isinstance(year, int) or not 1900 <= year <= 2200):
            errors.add("graduation_year", "must be null or an integer from 1900 to 2200")
        else:
            profile.graduation_year = year
    if "show_transaction_history" in body:
        value = body["show_transaction_history"]
        if not isinstance(value, bool):
            errors.add("show_transaction_history", "must be true or false")
        else:
            profile.show_transaction_history = value
    errors.raise_if_any()
    profile = current_profile()
    profile.display_name = display_name
    db.session.commit()
    return jsonify({"profile": profile.to_me_dict()})


@bp.after_request
def private(response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
