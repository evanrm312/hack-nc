"""GET/PATCH /api/me"""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..auth import current_profile, require_verified_user
from ..db import db
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
    display_name = string(body.get("display_name"), "display_name", errors, required=True, max_len=80)
    errors.raise_if_any()
    profile = current_profile()
    profile.display_name = display_name
    db.session.commit()
    return jsonify({"profile": profile.to_me_dict()})
