"""Atomic listing reservation. Owned by Person 1; consumed by Person 4.

One physical item has at most one active exchange. Every helper here is a
single conditional UPDATE, so it is atomic on both SQLite and PostgreSQL
without SELECT ... FOR UPDATE (which SQLite silently ignores).

Typical use inside the Person 4 accept flow, in the same transaction as the
exchange status change:

    from server.reservation import reserve_listing, ReservationConflict

    if both_accepted(offer):
        if not reserve_listing(db.session, exchange.listing_id, exchange.id):
            raise ReservationConflict(...)   # map to 409 reservation_conflict
        exchange.status = "reserved"
        db.session.commit()

The helpers do NOT commit; the caller owns the transaction.
"""

from __future__ import annotations

from sqlalchemy import update

from .models import Listing


class ReservationConflict(Exception):
    """The listing is no longer available (someone else reserved it first)."""


def reserve_listing(session, listing_id: str, exchange_id: str) -> bool:
    """Move an available listing to reserved for ``exchange_id``.

    Returns True if this call won the reservation. Returns True as well if the
    listing is already reserved by the *same* exchange (idempotent repeat
    presses). Returns False if another exchange holds it or it is sold/withdrawn.
    """
    result = session.execute(
        update(Listing)
        .where(
            Listing.id == listing_id,
            Listing.status == "available",
            Listing.active_exchange_id.is_(None),
        )
        .values(status="reserved", active_exchange_id=exchange_id)
    )
    if result.rowcount == 1:
        return True
    session.flush()
    listing = session.get(Listing, listing_id)
    return bool(listing and listing.status == "reserved" and listing.active_exchange_id == exchange_id)


def release_listing(session, listing_id: str, exchange_id: str) -> bool:
    """Release a reservation held by ``exchange_id`` (cancel before pickup, or
    a completed loan returning the item). A stale call from a different
    exchange is a no-op. Returns True if a row changed."""
    result = session.execute(
        update(Listing)
        .where(
            Listing.id == listing_id,
            Listing.status == "reserved",
            Listing.active_exchange_id == exchange_id,
        )
        .values(status="available", active_exchange_id=None)
    )
    return result.rowcount == 1


def mark_listing_sold(session, listing_id: str, exchange_id: str) -> bool:
    """Completed sale: reserved -> sold, only for the exchange holding it."""
    result = session.execute(
        update(Listing)
        .where(
            Listing.id == listing_id,
            Listing.status == "reserved",
            Listing.active_exchange_id == exchange_id,
        )
        .values(status="sold")
    )
    return result.rowcount == 1
