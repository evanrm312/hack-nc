"""Evidence-backed confirmations using Person 1's existing persisted schema.

Each action acknowledges condition and confirms possession together. The
acknowledgment timestamp on every reviewed photo records that joint action;
no messages, offer terms, or shared schema fields are repurposed.
"""

from ..db import db, iso_utc, utcnow
from ..errors import ApiError
from ..models import Evidence

PICKUP_STAGES = ("pre_handoff", "handoff")
RETURN_STAGES = ("pre_return", "post_return")


def photos_for(exchange, stages):
    return list(db.session.scalars(
        db.select(Evidence).where(Evidence.exchange_id == exchange.id, Evidence.stage.in_(stages))
        .order_by(Evidence.created_at, Evidence.id)
    ))


def confirmations_for(exchange, stage, *, photos=None):
    stages = PICKUP_STAGES if stage == "handoff" else RETURN_STAGES
    photos = photos_for(exchange, stages) if photos is None else [photo for photo in photos if photo.stage in stages]
    if not photos:
        return []
    confirmations = []
    for participant_id in sorted(exchange.participant_ids):
        timestamps = [(photo.acknowledged_by or {}).get(participant_id) for photo in photos]
        if all(timestamps):
            timestamp = max(timestamps)
            confirmations.append({
                "stage": stage, "participant_id": participant_id,
                "condition_acknowledged_at": timestamp, "confirmed_at": timestamp,
                "evidence_ids": [photo.id for photo in photos],
            })
    return confirmations


def acknowledge_and_confirm(photos, user_id):
    timestamp = iso_utc(utcnow())
    for photo in photos:
        # Assign a new dict so SQLAlchemy persists the JSON change.
        if user_id not in (photo.acknowledged_by or {}):
            photo.acknowledged_by = {**(photo.acknowledged_by or {}), user_id: timestamp}


def require_pickup_photos(exchange):
    photos = photos_for(exchange, PICKUP_STAGES)
    if not photos:
        raise ApiError(409, "missing_evidence", "Upload pickup condition photos before confirming handoff")
    return photos


def require_return_photos(exchange, *, before_only=False):
    photos = photos_for(exchange, RETURN_STAGES)
    before = any(photo.stage == "pre_return" and photo.uploader_id == exchange.requester_id for photo in photos)
    after = any(photo.stage == "post_return" and photo.uploader_id == exchange.owner_id for photo in photos)
    if not before or (not before_only and not after):
        raise ApiError(409, "missing_evidence", "Return requires before-return borrower photos"
                       + ("" if before_only else " and after-return owner photos"))
    return photos


def ensure_photos_open(exchange, stage):
    stages = PICKUP_STAGES if stage in PICKUP_STAGES else RETURN_STAGES
    if any(photo.acknowledged_by for photo in photos_for(exchange, stages)):
        raise ApiError(409, "evidence_locked", "Condition photos are locked after the first confirmation")


def invalid_transition():
    return ApiError(409, "invalid_transition", "This action is not allowed at the current exchange stage")
