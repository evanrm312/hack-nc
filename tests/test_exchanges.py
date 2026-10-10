"""Person 4: private negotiations and atomic mutual acceptance."""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Barrier

import pytest

from server.db import db
from server.models import Evidence, Exchange, Listing, MeetingSpot, OfferRevision
from server.storage import get_storage
from tests.conftest import auth, create_listing


@pytest.fixture
def third_party(app, client):
    app.config["SANDBOX_USERS"].append("charlie@unc.edu")
    headers = auth("charlie@unc.edu")
    assert client.get("/api/me", headers=headers).status_code == 200
    return headers


@pytest.fixture
def spot():
    meeting = MeetingSpot(label="Union lobby", public_area="Central campus", is_active=True)
    db.session.add(meeting)
    db.session.commit()
    return meeting.id


def start(client, listing_id, headers, mode="borrow", **extra):
    response = client.post("/api/exchanges", headers=headers, json={
        "listing_id": listing_id, "mode": mode, **extra,
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def propose(client, exchange_id, headers, **terms):
    return client.post(f"/api/exchanges/{exchange_id}/offers", headers=headers, json=terms)


def accept(client, exchange_id, headers, version=2, **extra):
    return client.post(f"/api/exchanges/{exchange_id}/accept", headers=headers, json={"version": version, **extra})


def ready_exchange(client, alice, bob, spot, mode="borrow", listing_id=None, **terms):
    listing_id = listing_id or create_listing(client, alice)["id"]
    exchange = start(client, listing_id, bob, mode)["exchange"]
    meetings = {"pickup_meeting_spot_id": spot, "pickup_at": "2026-10-12T18:00:00Z"}
    if mode == "borrow":
        meetings.update(return_meeting_spot_id=spot, return_deadline="2026-10-15T22:00:00Z")
    response = propose(client, exchange["id"], bob, **meetings, **terms)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["exchange"]


def test_creation_uses_real_listing_identity_and_preserves_unknowns(client, alice, bob):
    listing = create_listing(client, alice, condition=None)
    result = start(client, listing["id"], bob, owner_id="fake", requester_id="fake", status="completed")
    offer = result["current_offer"]
    assert result["exchange"]["owner_id"] == listing["owner_id"]
    assert result["exchange"]["requester_id"] == client.get("/api/me", headers=bob).get_json()["profile"]["id"]
    assert result["exchange"]["status"] == "negotiating"
    assert offer["deposit_cents"] == offer["agreed_item_value_cents"] == 20000
    assert offer["condition_snapshot"]["condition"] is None
    assert offer["pickup_at"] is None
    assert offer["pickup_meeting_spot_id"] is None
    detail = client.get(f"/api/exchanges/{result['exchange']['id']}", headers=bob).get_json()
    assert "fixture" not in detail
    assert detail["offers"][0]["id"] == offer["id"]
    assert "no real funds are reserved or charged" in detail["simulation_notice"]


def test_create_rejects_owner_unavailable_or_unsupported_mode(client, alice, bob):
    listing = create_listing(client, alice, allowed_modes=["borrow"])
    payload = {"listing_id": listing["id"], "mode": "borrow"}
    assert client.post("/api/exchanges", json=payload).status_code == 401
    assert client.post("/api/exchanges", json=payload, headers=alice).status_code == 403
    assert client.post("/api/exchanges", json={**payload, "mode": "sale"}, headers=bob).status_code == 400
    assert client.post("/api/exchanges", json={**payload, "listing_id": "missing"}, headers=bob).status_code == 404
    client.patch(f"/api/listings/{listing['id']}", json={"status": "withdrawn"}, headers=alice)
    response = client.post("/api/exchanges", json=payload, headers=bob)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "reservation_conflict"


def test_source_request_must_belong_to_requester(client, alice, bob):
    listing = create_listing(client, alice)
    source = client.post("/api/requests", json={"original_text": "Suit", "modes": ["borrow"]}, headers=alice).get_json()["request"]
    response = client.post("/api/exchanges", headers=bob, json={
        "listing_id": listing["id"], "mode": "borrow", "source_request_id": source["id"],
    })
    assert response.status_code == 404


def test_third_party_cannot_read_or_mutate_exchange_messages_or_evidence(client, alice, bob, third_party, spot):
    exchange = ready_exchange(client, alice, bob, spot)
    base = f"/api/exchanges/{exchange['id']}"
    for suffix in ("", "/messages", "/evidence", "/evidence/unknown"):
        response = client.get(base + suffix, headers=third_party)
        assert response.status_code == 403, suffix
        assert response.get_json()["error"]["code"] == "forbidden"
        assert response.headers["Cache-Control"] == "private, no-store"
    for suffix in ("messages", "offers", "accept", "evidence", "handoff", "return", "review", "cancel", "dispute"):
        assert client.post(base + "/" + suffix, json={}, headers=third_party).status_code == 403, suffix
    assert client.get("/api/exchanges", headers=third_party).get_json() == {"exchanges": []}
    for headers in (alice, bob):
        listed = client.get("/api/exchanges", headers=headers).get_json()["exchanges"]
        assert [row["id"] for row in listed] == [exchange["id"]]
        assert listed[0]["listing"]["title"] == "Navy suit 40R"


def test_real_evidence_is_scoped_and_never_public(client, alice, bob, third_party, spot):
    exchange = ready_exchange(client, alice, bob, spot)
    other = ready_exchange(client, alice, bob, spot)
    stored = get_storage().save("private", BytesIO(b"\x89PNG\r\n\x1a\nprivate-photo"), 1024)
    photo = Evidence(exchange_id=exchange["id"], uploader_id=exchange["owner_id"], stage="pre_handoff", private_storage_path=stored.path, content_type=stored.content_type)
    db.session.add(photo)
    db.session.commit()
    url = photo.to_dict()["url"]
    assert client.get(url, headers=alice).data == b"\x89PNG\r\n\x1a\nprivate-photo"
    assert client.get(url, headers=bob).status_code == 200
    assert client.get(url, headers=third_party).status_code == 403
    assert client.get(f"/api/exchanges/{other['id']}/evidence/{photo.id}", headers=bob).status_code == 404
    assert client.get(f"/media/public/{stored.path}").status_code == 404
    assert "private_storage_path" not in client.get(f"/api/exchanges/{exchange['id']}/evidence", headers=bob).get_json()["evidence"][0]


def test_private_messages_derive_sender_and_poll_same_second_safely(client, alice, bob, spot):
    exchange = ready_exchange(client, alice, bob, spot)
    base = f"/api/exchanges/{exchange['id']}/messages"
    response = client.post(base, json={"body": " <script>alert('x')</script> ", "sender_id": exchange["owner_id"]}, headers=bob)
    assert response.status_code == 201
    message = response.get_json()["message"]
    assert message["sender_id"] == exchange["requester_id"]
    assert message["body"] == "<script>alert('x')</script>"
    for body in (" ", 3, "x" * 4001):
        assert client.post(base, json={"body": body}, headers=bob).status_code == 400
    assert client.get(base + "?after=naive", headers=alice).status_code == 400
    polled = client.get(base, query_string={"after": message["created_at"]}, headers=alice).get_json()["messages"]
    assert [row["id"] for row in polled] == [message["id"]]


@pytest.mark.parametrize("terms", [
    {"rental_fee_cents": -1}, {"deposit_cents": 0.5}, {"deposit_cents": True},
    {"deposit_cents": 20001}, {"agreed_item_value_cents": None},
    {"pickup_meeting_spot_id": "missing"}, {"pickup_at": "2026-10-12T18:00:00"},
    {"pickup_at": "2026-10-12T18:00:00.500Z"},
    {"return_deadline": "2026-10-12T18:00:00Z"}, {"condition_snapshot": []},
    {"condition_snapshot": {"condition": "invented", "accessories": "bag"}},
    {"price_reference_id": "invented-evidence"}, {"sale_price_cents": 9000},
])
def test_invalid_offers_do_not_change_revision(client, alice, bob, spot, terms):
    exchange = ready_exchange(client, alice, bob, spot)
    response = propose(client, exchange["id"], bob, **terms)
    assert response.status_code == 400, response.get_json()
    assert client.get(f"/api/exchanges/{exchange['id']}", headers=bob).get_json()["exchange"]["current_offer_revision"] == 2


def test_incomplete_offer_cannot_be_accepted(client, alice, bob):
    exchange = start(client, create_listing(client, alice)["id"], bob)["exchange"]
    response = accept(client, exchange["id"], bob, version=1)
    assert response.status_code == 400
    assert "pickup_at" in response.get_json()["error"]["fields"]


def test_changed_terms_clear_acceptances_and_lender_acknowledgment(client, alice, bob, spot):
    exchange = ready_exchange(client, alice, bob, spot, deposit_cents=6000)
    accepted = accept(client, exchange["id"], alice, lower_deposit_acknowledged=True)
    assert accepted.status_code == 200
    response = propose(client, exchange["id"], bob, rental_fee_cents=1600, owner_accepted_at="fake", requester_accepted_at="fake", lower_deposit_acknowledged=True)
    assert response.status_code == 201
    offer = response.get_json()["offer"]
    assert offer["version"] == 3
    assert offer["owner_accepted_at"] is None
    assert offer["requester_accepted_at"] is None
    assert offer["lower_deposit_acknowledged"] is False
    assert accept(client, exchange["id"], bob, version=2).get_json()["error"]["code"] == "stale_offer"
    assert accept(client, exchange["id"], bob, version=3).status_code == 200
    reset = propose(client, exchange["id"], alice, deposit_cents=7000).get_json()["offer"]
    assert reset["owner_accepted_at"] is None and reset["requester_accepted_at"] is None
    history = client.get(f"/api/exchanges/{exchange['id']}", headers=bob).get_json()["offers"]
    assert history[1]["owner_accepted_at"] is not None
    assert history[1]["deposit_cents"] == 6000


@pytest.mark.parametrize("terms", [
    {"pickup_at": "2026-10-13T18:00:00Z"}, {"return_deadline": "2026-10-16T22:00:00Z"},
    {"condition_snapshot": {"condition": None, "accessories": None, "known_defects": None}},
    {"agreed_item_value_cents": 22000},
])
def test_each_changed_term_creates_a_revision(client, alice, bob, spot, terms):
    exchange = ready_exchange(client, alice, bob, spot)
    assert accept(client, exchange["id"], bob).status_code == 200
    response = propose(client, exchange["id"], alice, **terms)
    assert response.status_code == 201
    assert response.get_json()["offer"]["version"] == 3
    assert response.get_json()["offer"]["requester_accepted_at"] is None


def test_meeting_change_resets_acceptance_and_inactive_spot_is_rejected(client, alice, bob, spot):
    exchange = ready_exchange(client, alice, bob, spot)
    assert accept(client, exchange["id"], bob).status_code == 200
    other = MeetingSpot(label="Library entrance", public_area="Central campus", is_active=True)
    db.session.add(other)
    db.session.commit()
    response = propose(client, exchange["id"], alice, pickup_meeting_spot_id=other.id)
    assert response.status_code == 201
    assert response.get_json()["offer"]["requester_accepted_at"] is None
    other.is_active = False
    db.session.commit()
    assert accept(client, exchange["id"], alice, version=3).status_code == 400


def test_fee_only_api_edit_preserves_exact_meeting_times(client, alice, bob, spot):
    exchange = ready_exchange(client, alice, bob, spot)
    response = propose(client, exchange["id"], alice,
                       pickup_at="2026-10-12T18:00:37Z", return_deadline="2026-10-15T22:00:49Z")
    assert response.status_code == 201
    response = propose(client, exchange["id"], bob, rental_fee_cents=1600)
    assert response.status_code == 201
    assert response.get_json()["offer"]["pickup_at"] == "2026-10-12T18:00:37Z"
    assert response.get_json()["offer"]["return_deadline"] == "2026-10-15T22:00:49Z"


@pytest.mark.parametrize("status", ["on_loan", "return_pending", "completed", "disputed", "cancelled"])
def test_other_states_cannot_negotiate_or_accept(client, alice, bob, spot, status):
    exchange = ready_exchange(client, alice, bob, spot)
    db.session.get(Exchange, exchange["id"]).status = status
    db.session.commit()
    assert propose(client, exchange["id"], bob, rental_fee_cents=1700).status_code == 409
    assert accept(client, exchange["id"], bob).status_code == 409
    assert db.session.get(Exchange, exchange["id"]).status == status


def test_unchanged_terms_keep_acceptance_and_duplicate_accept_is_idempotent(client, alice, bob, spot):
    exchange = ready_exchange(client, alice, bob, spot)
    first = accept(client, exchange["id"], bob).get_json()["current_offer"]
    repeat = accept(client, exchange["id"], bob).get_json()["current_offer"]
    assert repeat == first
    unchanged = propose(client, exchange["id"], bob, pickup_at="2026-10-12T14:00:00-04:00")
    assert unchanged.status_code == 200
    assert unchanged.get_json()["offer"] == first
    assert accept(client, exchange["id"], alice).get_json()["exchange"]["status"] == "reserved"
    assert accept(client, exchange["id"], alice).get_json()["exchange"]["status"] == "reserved"
    assert accept(client, exchange["id"], bob).get_json()["exchange"]["status"] == "reserved"
    assert len(db.session.scalars(db.select(OfferRevision).where(OfferRevision.exchange_id == exchange["id"])).all()) == 2
    assert propose(client, exchange["id"], alice, deposit_cents=5000).status_code == 409


@pytest.mark.parametrize("ack", [None, False, "true", 1])
def test_low_deposit_requires_explicit_owner_boolean(client, alice, bob, spot, ack):
    exchange = ready_exchange(client, alice, bob, spot, deposit_cents=6000)
    assert accept(client, exchange["id"], bob, lower_deposit_acknowledged=True).status_code == 200
    response = accept(client, exchange["id"], alice, lower_deposit_acknowledged=ack)
    assert response.status_code == 400
    current = client.get(f"/api/exchanges/{exchange['id']}", headers=bob).get_json()["current_offer"]
    assert current["owner_accepted_at"] is None
    assert current["lower_deposit_acknowledged"] is False
    assert current["uncovered_value_cents"] == 14000
    response = accept(client, exchange["id"], alice, lower_deposit_acknowledged=True)
    assert response.get_json()["exchange"]["status"] == "reserved"
    detail = client.get(f"/api/exchanges/{exchange['id']}", headers=bob).get_json()
    assert detail["deposit_status"]["state"] == "simulated_held"
    assert "no real funds" in detail["deposit_status"]["label"]


def test_sale_has_no_loan_fields_and_reserves_without_collateral(client, alice, bob, spot):
    exchange = ready_exchange(client, alice, bob, spot, mode="sale")
    assert propose(client, exchange["id"], alice, rental_fee_cents=0).status_code == 400
    assert propose(client, exchange["id"], alice, return_meeting_spot_id=spot).status_code == 400
    assert accept(client, exchange["id"], alice).status_code == 200
    result = accept(client, exchange["id"], bob).get_json()
    assert result["exchange"]["status"] == "reserved"
    for field in ("rental_fee_cents", "agreed_item_value_cents", "deposit_cents", "return_deadline"):
        assert result["current_offer"][field] is None


def test_free_loan_and_zero_deposit_require_lender_ack(client, alice, bob, spot):
    exchange = ready_exchange(client, alice, bob, spot, rental_fee_cents=0, deposit_cents=0)
    assert accept(client, exchange["id"], alice).status_code == 400
    assert accept(client, exchange["id"], alice, lower_deposit_acknowledged=True).status_code == 200
    assert accept(client, exchange["id"], bob).get_json()["exchange"]["status"] == "reserved"


def test_competing_accepts_reserve_exactly_once_and_roll_back_loser(app, client, alice, bob, third_party, spot):
    listing = create_listing(client, alice)
    first = ready_exchange(client, alice, bob, spot, listing_id=listing["id"])
    second = ready_exchange(client, alice, third_party, spot, listing_id=listing["id"])
    for exchange in (first, second):
        assert accept(client, exchange["id"], alice).status_code == 200
    db.session.remove()
    barrier = Barrier(2)

    def compete(exchange, headers):
        with app.test_client() as independent_client:
            barrier.wait(timeout=5)
            response = accept(independent_client, exchange["id"], headers)
            return exchange["id"], response.status_code, response.get_json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(compete, first, bob), pool.submit(compete, second, third_party)]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(row[1] for row in results) == [200, 409], results
    winner = next(row for row in results if row[1] == 200)
    loser = next(row for row in results if row[1] == 409)
    assert loser[2]["error"]["code"] == "reservation_conflict"
    held = db.session.get(Listing, listing["id"])
    assert held.status == "reserved" and held.active_exchange_id == winner[0]
    assert db.session.get(Exchange, winner[0]).status == "reserved"
    assert db.session.get(Exchange, loser[0]).status == "negotiating"
    loser_offer = db.session.scalar(db.select(OfferRevision).where(OfferRevision.exchange_id == loser[0], OfferRevision.version == 2))
    assert loser_offer.requester_accepted_at is None


def test_simultaneous_participant_acceptances_do_not_get_lost(app, client, alice, bob, spot):
    exchange = ready_exchange(client, alice, bob, spot)
    db.session.remove()
    barrier = Barrier(2)

    def confirm(headers):
        with app.test_client() as independent_client:
            barrier.wait(timeout=5)
            response = accept(independent_client, exchange["id"], headers)
            return response.status_code, response.get_json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(confirm, headers) for headers in (alice, bob)]
        results = [future.result(timeout=15) for future in futures]
    assert [row[0] for row in results] == [200, 200], results
    detail = client.get(f"/api/exchanges/{exchange['id']}", headers=bob).get_json()
    assert detail["exchange"]["status"] == "reserved"
    assert detail["current_offer"]["owner_accepted_at"]
    assert detail["current_offer"]["requester_accepted_at"]


def test_edit_racing_accept_cannot_reserve_stale_terms(app, client, alice, bob, spot):
    exchange = ready_exchange(client, alice, bob, spot)
    assert accept(client, exchange["id"], alice).status_code == 200
    db.session.remove()
    barrier = Barrier(2)

    def edit():
        with app.test_client() as independent_client:
            barrier.wait(timeout=5)
            return propose(independent_client, exchange["id"], alice, rental_fee_cents=1600).status_code

    def confirm():
        with app.test_client() as independent_client:
            barrier.wait(timeout=5)
            return accept(independent_client, exchange["id"], bob).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        edit_future, accept_future = pool.submit(edit), pool.submit(confirm)
        result = (edit_future.result(timeout=15), accept_future.result(timeout=15))
    assert result in ((201, 409), (409, 200))
    detail = client.get(f"/api/exchanges/{exchange['id']}", headers=bob).get_json()
    if result == (201, 409):
        assert detail["exchange"]["status"] == "negotiating"
        assert detail["current_offer"]["owner_accepted_at"] is None
        assert detail["current_offer"]["requester_accepted_at"] is None
    else:
        assert detail["exchange"]["status"] == "reserved"
        assert detail["current_offer"]["rental_fee_cents"] == 1500


def test_later_milestones_never_silently_complete_or_charge(client, alice, bob, spot):
    exchange = ready_exchange(client, alice, bob, spot)
    for suffix in ("handoff", "return", "review", "dispute", "cancel", "evidence"):
        assert client.post(f"/api/exchanges/{exchange['id']}/{suffix}", json={}, headers=bob).status_code == 501
    assert db.session.get(Exchange, exchange["id"]).status == "negotiating"


@pytest.mark.parametrize("version", [None, True, 2.0, "2", 0, -1])
def test_accept_requires_integer_revision(client, alice, bob, spot, version):
    exchange = ready_exchange(client, alice, bob, spot)
    assert accept(client, exchange["id"], bob, version=version).status_code == 400


def test_preview_uses_isolated_labeled_data_and_does_not_duplicate_inventory(tmp_path):
    from server.exchanges.preview import create_preview_app

    data_dir = tmp_path / "preview"
    for _ in range(2):
        preview = create_preview_app(data_dir)
        assert preview.config["AUTH_MODE"] == "sandbox"
        assert preview.config["SQLALCHEMY_DATABASE_URI"] == f"sqlite:///{data_dir / 'preview.sqlite3'}"
        client = preview.test_client()
        alice = auth("alice@unc.edu")
        profile = client.get("/api/me", headers=alice).get_json()["profile"]
        assert profile["is_demo"] is True
        assert profile["badge"] == "Sandbox identity (not verified)"
        listings = client.get(f"/api/listings?owner_id={profile['id']}").get_json()["listings"]
        assert len(listings) == 2
        assert all("demo inventory" in listing["title"] for listing in listings)
        assert all(listing["status"] == "available" for listing in listings)
        assert client.get("/api/exchanges", headers=alice).get_json() == {"exchanges": []}
        assert b"Sandbox preview" in client.get("/exchanges").data
