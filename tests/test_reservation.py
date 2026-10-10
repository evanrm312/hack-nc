"""Atomic reservation helper: one active exchange per physical item."""

from server.db import db
from server.models import Listing
from server.reservation import mark_listing_sold, release_listing, reserve_listing
from tests.conftest import create_listing


def _listing(client, alice) -> Listing:
    data = create_listing(client, alice)
    return db.session.get(Listing, data["id"])


def test_only_one_of_two_competing_reservations_wins(client, alice):
    listing = _listing(client, alice)
    first = reserve_listing(db.session, listing.id, "exchange-A")
    second = reserve_listing(db.session, listing.id, "exchange-B")
    db.session.commit()
    assert first is True
    assert second is False
    db.session.refresh(listing)
    assert listing.status == "reserved"
    assert listing.active_exchange_id == "exchange-A"


def test_repeat_reservation_by_same_exchange_is_idempotent(client, alice):
    listing = _listing(client, alice)
    assert reserve_listing(db.session, listing.id, "exchange-A") is True
    assert reserve_listing(db.session, listing.id, "exchange-A") is True
    db.session.commit()
    db.session.refresh(listing)
    assert listing.active_exchange_id == "exchange-A"


def test_release_only_by_holding_exchange(client, alice):
    listing = _listing(client, alice)
    reserve_listing(db.session, listing.id, "exchange-A")
    db.session.commit()
    assert release_listing(db.session, listing.id, "exchange-B") is False
    db.session.refresh(listing)
    assert listing.status == "reserved"
    assert release_listing(db.session, listing.id, "exchange-A") is True
    db.session.commit()
    db.session.refresh(listing)
    assert listing.status == "available"
    assert listing.active_exchange_id is None
    # Released item can be reserved again by someone else.
    assert reserve_listing(db.session, listing.id, "exchange-B") is True


def test_sold_listing_cannot_be_reserved(client, alice):
    listing = _listing(client, alice)
    reserve_listing(db.session, listing.id, "exchange-A")
    assert mark_listing_sold(db.session, listing.id, "exchange-B") is False
    assert mark_listing_sold(db.session, listing.id, "exchange-A") is True
    db.session.commit()
    db.session.refresh(listing)
    assert listing.status == "sold"
    assert reserve_listing(db.session, listing.id, "exchange-C") is False
    assert release_listing(db.session, listing.id, "exchange-A") is False


def test_withdrawn_listing_cannot_be_reserved(client, alice):
    listing = _listing(client, alice)
    listing.status = "withdrawn"
    db.session.commit()
    assert reserve_listing(db.session, listing.id, "exchange-A") is False


def test_reserved_listing_cannot_be_edited_via_api(client, alice):
    listing = _listing(client, alice)
    reserve_listing(db.session, listing.id, "exchange-A")
    db.session.commit()
    resp = client.patch(f"/api/listings/{listing.id}", json={"title": "nope"}, headers=alice)
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "listing_locked"
    assert client.get("/api/listings").get_json()["listings"] == []
    assert client.get("/api/listings?status=reserved").get_json()["listings"][0]["id"] == listing.id
