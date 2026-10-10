"""Read-only public marketplace catalog."""

from datetime import timezone

from flask import Blueprint, abort, current_app, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

from server.db import db
from server.models import Listing

catalog_bp = Blueprint("catalog", __name__, url_prefix="/api/listings")
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_PAGE = 10_000


def _utc_iso(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def serialize_public_listing(listing):
    """Return an explicit allowlist of fields safe for anonymous browsing."""
    return {
        "id": listing.id,
        "title": listing.title,
        "category": listing.category,
        "description": listing.description,
        "specifications": listing.specifications,
        "condition": listing.condition,
        "accessories": listing.accessories,
        "modes": [listing.mode] if listing.mode != "both" else ["sale", "borrow"],
        "sale_price_cents": listing.sale_price_cents,
        "rental_fee_cents": listing.rental_fee_cents,
        "proposed_item_value_cents": listing.proposed_item_value_cents,
        "collateral_percent": listing.collateral_percent,
        "public_photo_path": listing.public_photo_path,
        "owner_display_name": listing.owner.display_name,
        "is_demo": listing.is_demo,
        "created_at": _utc_iso(listing.created_at),
    }


def _database_unavailable():
    return jsonify({
        "error": {
            "code": "database_unavailable",
            "message": "The catalog is temporarily unavailable.",
            "fields": {},
        }
    }), 503


def _positive_int(name, default, maximum=None):
    raw = request.args.get(name)
    if raw is None:
        return default
    if len(raw) > 9 or not raw.isascii() or not raw.isdecimal():
        return None
    value = int(raw)
    if value < 1 or (maximum is not None and value > maximum):
        return None
    return value


@catalog_bp.get("")
def list_listings():
    page = _positive_int("page", 1, MAX_PAGE)
    per_page = _positive_int("per_page", DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE)
    if page is None or per_page is None:
        fields = {}
        if page is None:
            fields["page"] = f"Must be an integer from 1 to {MAX_PAGE}."
        if per_page is None:
            fields["per_page"] = f"Must be an integer from 1 to {MAX_PAGE_SIZE}."
        return jsonify({
            "error": {
                "code": "invalid_input",
                "message": "Invalid pagination parameters.",
                "fields": fields,
            }
        }), 400
    if not current_app.config.get("SQLALCHEMY_DATABASE_URI"):
        return _database_unavailable()

    try:
        active = Listing.status == "active"
        total = db.session.scalar(select(func.count()).select_from(Listing).where(active))
        statement = (
            select(Listing)
            .options(joinedload(Listing.owner))
            .where(active)
            .order_by(Listing.created_at.desc(), Listing.id.asc())
            .limit(per_page)
            .offset((page - 1) * per_page)
        )
        listings = db.session.execute(statement).scalars().all()
    except SQLAlchemyError:
        db.session.rollback()
        return _database_unavailable()

    return jsonify({
        "items": [serialize_public_listing(listing) for listing in listings],
        "page": page,
        "per_page": per_page,
        "total": total,
    })


@catalog_bp.get("/<string:listing_id>")
def get_listing(listing_id):
    if not current_app.config.get("SQLALCHEMY_DATABASE_URI"):
        return _database_unavailable()
    try:
        listing = db.session.execute(
            select(Listing)
            .options(joinedload(Listing.owner))
            .where(Listing.id == listing_id, Listing.status == "active")
        ).scalar_one_or_none()
    except SQLAlchemyError:
        db.session.rollback()
        return _database_unavailable()
    if listing is None:
        abort(404)
    return jsonify(serialize_public_listing(listing))
