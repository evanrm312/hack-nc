"""Offer terms and validation for the negotiating → reserved milestone."""

from __future__ import annotations

from datetime import timezone

from ..db import db
from ..models import MeetingSpot
from ..validation import FieldErrors, datetime_utc, money_cents, string, string_list

MONEY_FIELDS = (
    "sale_price_cents", "rental_fee_cents", "agreed_item_value_cents", "deposit_cents",
)
MEETING_FIELDS = ("pickup_meeting_spot_id", "return_meeting_spot_id")
DATE_FIELDS = ("pickup_at", "return_deadline")
TERM_FIELDS = MONEY_FIELDS + MEETING_FIELDS + DATE_FIELDS + ("condition_snapshot",)
CONDITIONS = ("new", "like_new", "good", "fair", "worn")


def terms_from_offer(offer) -> dict:
    return {field: getattr(offer, field) for field in TERM_FIELDS}


def initial_terms(listing, mode: str) -> dict:
    """Listing proposals are not accepted terms. Meeting details stay unknown."""
    value = listing.proposed_item_value_cents if mode == "borrow" else None
    collateral = listing.collateral_percent if listing.collateral_percent is not None else 100
    return {
        "sale_price_cents": listing.sale_price_cents if mode == "sale" else None,
        "rental_fee_cents": listing.rental_fee_cents if mode == "borrow" else None,
        "agreed_item_value_cents": value,
        # Round the owner's proposed percentage to the nearest integer cent.
        "deposit_cents": (value * collateral + 50) // 100 if value is not None else None,
        "pickup_meeting_spot_id": None,
        "return_meeting_spot_id": None,
        "pickup_at": None,
        "return_deadline": None,
        "condition_snapshot": {
            "condition": listing.condition,
            "accessories": listing.accessories,
            "known_defects": listing.known_defects,
        },
    }


def validate_terms(data: dict, mode: str, *, complete: bool = False) -> dict:
    errors = FieldErrors()
    terms = {}
    required_money = {"sale_price_cents"} if mode == "sale" else set(MONEY_FIELDS[1:])
    for field in MONEY_FIELDS:
        terms[field] = money_cents(data.get(field), field, errors, required=field in required_money)
        if field not in required_money and data.get(field) is not None:
            errors.add(field, f"not used for {mode} exchanges")

    value, deposit = terms["agreed_item_value_cents"], terms["deposit_cents"]
    if value is not None and deposit is not None and deposit > value:
        errors.add("deposit_cents", "must not exceed the agreed item value")

    for field in MEETING_FIELDS:
        spot_id = string(data.get(field), field, errors, max_len=32)
        if spot_id:
            spot = db.session.get(MeetingSpot, spot_id)
            if spot is None or not spot.is_active:
                errors.add(field, "select an active campus meeting spot")
        terms[field] = spot_id

    for field in DATE_FIELDS:
        value = data.get(field)
        # Internal datetime values are serialized before using the shared parser.
        if hasattr(value, "tzinfo"):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            value = value.isoformat()
        terms[field] = datetime_utc(value, field, errors)
        if terms[field] is not None and terms[field].microsecond:
            # The shared record serializer displays whole seconds. Reject finer
            # precision rather than agree to a time participants cannot review.
            errors.add(field, "meeting times must use whole seconds")

    if mode == "sale":
        for field in ("return_meeting_spot_id", "return_deadline"):
            if data.get(field) is not None:
                errors.add(field, "not used for sale exchanges")
    elif terms["pickup_at"] and terms["return_deadline"]:
        if terms["return_deadline"] <= terms["pickup_at"]:
            errors.add("return_deadline", "must be after pickup")

    if complete:
        required = ["pickup_meeting_spot_id", "pickup_at"]
        if mode == "borrow":
            required += ["return_meeting_spot_id", "return_deadline"]
        for field in required:
            if terms[field] is None:
                errors.add(field, "agree on this before accepting")

    snapshot = data.get("condition_snapshot")
    if not isinstance(snapshot, dict):
        errors.add("condition_snapshot", "must be an object")
        snapshot = {}
    condition = snapshot.get("condition")
    if condition is not None and condition not in CONDITIONS:
        errors.add("condition_snapshot.condition", "select a known condition or leave unknown")
    terms["condition_snapshot"] = {"condition": condition}
    for field in ("accessories", "known_defects"):
        terms["condition_snapshot"][field] = string_list(
            snapshot.get(field), f"condition_snapshot.{field}", errors
        )

    errors.raise_if_any()
    return terms


def same_terms(left: dict, right: dict) -> bool:
    """SQLite returns naive UTC datetimes; compare normalized instants."""
    for field in TERM_FIELDS:
        a, b = left[field], right[field]
        if field in DATE_FIELDS:
            if a is not None and a.tzinfo is None:
                a = a.replace(tzinfo=timezone.utc)
            if b is not None and b.tzinfo is None:
                b = b.replace(tzinfo=timezone.utc)
        if a != b:
            return False
    return True
