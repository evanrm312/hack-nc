"""Person 4: private negotiations, evidence, pickup, and return."""

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


def test_invalid_milestones_never_silently_complete_or_charge(client, alice, bob, spot):
    exchange = ready_exchange(client, alice, bob, spot)
    for suffix in ("dispute", "cancel"):
        assert client.post(f"/api/exchanges/{exchange['id']}/{suffix}", json={}, headers=bob).status_code == 400
    assert client.post(f"/api/exchanges/{exchange['id']}/review", json={}, headers=bob).status_code == 409
    for suffix in ("handoff", "return", "evidence"):
        assert client.post(f"/api/exchanges/{exchange['id']}/{suffix}", json={}, headers=bob).status_code in (400, 409)
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


def image_bytes():
    """A real, decodable 2x2 PNG; no image library needed by the fixtures."""
    import struct
    import zlib

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\x00\xff\x00" * 2))
            + chunk(b"IEND", b""))


def photo_upload(client, exchange_id, headers, stage="pre_handoff", data=None):
    return client.post(f"/api/exchanges/{exchange_id}/evidence", headers=headers, data={
        "stage": stage, "photo": (BytesIO(image_bytes() if data is None else data), "misleading.txt", "text/plain"),
    })


def reserved_exchange(client, alice, bob, spot, mode="borrow"):
    exchange = ready_exchange(client, alice, bob, spot, mode=mode)
    assert accept(client, exchange["id"], alice).status_code == 200
    assert accept(client, exchange["id"], bob).status_code == 200
    return exchange


def handoff(client, exchange_id, headers, **body):
    return client.post(f"/api/exchanges/{exchange_id}/handoff", headers=headers,
                       json={"confirm": True, "accept_condition": True, **body})


def return_action(client, exchange_id, headers, action, **body):
    return client.post(f"/api/exchanges/{exchange_id}/return", headers=headers,
                       json={"action": action, **body})


def active_loan(client, alice, bob, spot):
    exchange = reserved_exchange(client, alice, bob, spot)
    assert photo_upload(client, exchange["id"], alice).status_code == 201
    assert handoff(client, exchange["id"], alice).status_code == 200
    assert handoff(client, exchange["id"], bob).get_json()["exchange"]["status"] == "on_loan"
    return exchange


def pending_return(client, alice, bob, spot):
    exchange = active_loan(client, alice, bob, spot)
    assert photo_upload(client, exchange["id"], bob, "pre_return").status_code == 201
    assert return_action(client, exchange["id"], bob, "initiate").status_code == 200
    return exchange


def test_uploaded_photos_are_private_persisted_and_content_detected(client, alice, bob, third_party, spot):
    exchange = reserved_exchange(client, alice, bob, spot)
    response = photo_upload(client, exchange["id"], alice)
    assert response.status_code == 201, response.get_json()
    photo = response.get_json()["evidence"]
    assert photo["content_type"] == "image/png"
    assert photo["exchange_id"] == exchange["id"] and photo["uploader_id"] == exchange["owner_id"]
    assert photo["stage"] == "pre_handoff" and photo["created_at"].endswith("Z")
    assert "private_storage_path" not in photo
    for headers in (alice, bob):
        result = client.get(photo["url"], headers=headers)
        assert result.data == image_bytes()
        assert result.headers["Content-Type"].startswith("image/png")
        assert result.headers["Cache-Control"] == "private, no-store"
        preview = client.get(photo["url"] + "?preview=1", headers=headers)
        assert preview.status_code == 200 and preview.get_json()["data_url"].startswith("data:image/")
    for suffix in ("", "?preview=1"):
        assert client.get(photo["url"] + suffix).status_code == 401
        assert client.get(photo["url"] + suffix, headers=third_party).status_code == 403
    assert photo_upload(client, exchange["id"], third_party).status_code == 403
    stored = db.session.get(Evidence, photo["id"])
    assert client.get("/media/public/" + stored.private_storage_path).status_code == 404
    other = ready_exchange(client, alice, bob, spot)
    assert client.get(f"/api/exchanges/{other['id']}/evidence/{photo['id']}?preview=1", headers=bob).status_code == 404


@pytest.mark.parametrize("data,code", [
    (b"", "validation_error"), (b"<svg><script>bad()</script></svg>", "unsupported_image"),
    (b"\x89PNG\r\n\x1a\nnot-an-image", "unsupported_image"),
    (b"\xff\xd8\xffnot-a-jpeg", "unsupported_image"),
    (b"RIFF\x00\x00\x00\x00WEBPnot-webp", "unsupported_image"),
])
def test_invalid_image_content_leaves_no_evidence(app, client, alice, bob, spot, data, code):
    from pathlib import Path

    exchange = reserved_exchange(client, alice, bob, spot)
    response = photo_upload(client, exchange["id"], bob, data=data)
    assert response.status_code == 400, response.get_json()
    assert response.get_json()["error"]["code"] == code
    assert client.get(f"/api/exchanges/{exchange['id']}/evidence", headers=bob).get_json()["evidence"] == []
    assert not list(Path(app.config["UPLOAD_DIR"], "private").rglob("*.*"))


def test_missing_file_stage_and_oversized_photo(client, app, alice, bob, spot):
    exchange = reserved_exchange(client, alice, bob, spot)
    base = f"/api/exchanges/{exchange['id']}/evidence"
    assert client.post(base, headers=bob, data={"stage": "pre_handoff"}).status_code == 400
    assert photo_upload(client, exchange["id"], bob, "invented").status_code == 400
    response = photo_upload(client, exchange["id"], bob, data=b"x" * (app.config["MAX_UPLOAD_BYTES"] + 1))
    assert response.status_code == 413 and response.get_json()["error"]["code"] == "payload_too_large"
    assert client.get(base, headers=bob).get_json()["evidence"] == []


@pytest.mark.parametrize("mode,expected,listing_status", [("sale", "completed", "sold"), ("borrow", "on_loan", "reserved")])
def test_pickup_requires_evidence_and_mutual_persisted_confirmations(client, alice, bob, spot, mode, expected, listing_status):
    exchange = reserved_exchange(client, alice, bob, spot, mode=mode)
    base = f"/api/exchanges/{exchange['id']}"
    assert handoff(client, exchange["id"], alice).get_json()["error"]["code"] == "missing_evidence"
    assert photo_upload(client, exchange["id"], bob, "handoff").status_code == 201
    first = handoff(client, exchange["id"], alice)
    assert first.status_code == 200 and first.get_json()["exchange"]["status"] == "reserved"
    saved = client.get(base, headers=bob).get_json()["confirmations"]
    assert len(saved) == 1 and saved[0]["condition_acknowledged_at"] and saved[0]["confirmed_at"]
    assert saved[0]["participant_id"] == exchange["owner_id"] and saved[0]["stage"] == "handoff"
    assert handoff(client, exchange["id"], alice).status_code == 200
    assert client.get(base, headers=alice).get_json()["confirmations"] == saved
    assert photo_upload(client, exchange["id"], alice).status_code == 409  # freeze the reviewed evidence
    assert handoff(client, exchange["id"], bob).get_json()["exchange"]["status"] == expected
    final = client.get(base, headers=bob).get_json()["confirmations"]
    assert len(final) == 2
    for headers in (alice, bob):
        assert handoff(client, exchange["id"], headers).status_code == 200
    assert client.get(base, headers=bob).get_json()["confirmations"] == final
    photos = client.get(base + "/evidence", headers=bob).get_json()["evidence"]
    assert set(photos[0]["acknowledged_by"]) == {exchange["owner_id"], exchange["requester_id"]}
    assert db.session.get(Listing, exchange["listing_id"]).status == listing_status


@pytest.mark.parametrize("body", [{"confirm": False}, {"confirm": "true"}, {"accept_condition": False}, {"accept_condition": 1}])
def test_pickup_requires_explicit_true_booleans(client, alice, bob, spot, body):
    exchange = reserved_exchange(client, alice, bob, spot)
    assert photo_upload(client, exchange["id"], alice).status_code == 201
    assert handoff(client, exchange["id"], alice, **body).status_code == 400
    assert client.get(f"/api/exchanges/{exchange['id']}", headers=bob).get_json()["confirmations"] == []


def test_return_requires_role_specific_photos_and_both_confirmations(client, alice, bob, spot):
    exchange = active_loan(client, alice, bob, spot)
    base = f"/api/exchanges/{exchange['id']}"
    assert return_action(client, exchange["id"], alice, "initiate").status_code == 403
    assert return_action(client, exchange["id"], bob, "initiate").get_json()["error"]["code"] == "missing_evidence"
    assert photo_upload(client, exchange["id"], alice, "pre_return").status_code == 403
    assert photo_upload(client, exchange["id"], bob, "post_return").status_code == 403
    assert photo_upload(client, exchange["id"], alice, "post_return").status_code == 409
    assert return_action(client, exchange["id"], bob, "accept").status_code == 409
    assert photo_upload(client, exchange["id"], bob, "pre_return").status_code == 201
    for _ in range(2):
        assert return_action(client, exchange["id"], bob, "initiate").get_json()["exchange"]["status"] == "return_pending"
    for headers in (alice, bob):
        assert return_action(client, exchange["id"], headers, "accept").get_json()["error"]["code"] == "missing_evidence"
    assert photo_upload(client, exchange["id"], bob, "pre_return").status_code == 409
    assert photo_upload(client, exchange["id"], alice, "post_return").status_code == 201
    assert return_action(client, exchange["id"], bob, "accept").get_json()["exchange"]["status"] == "return_pending"
    saved = client.get(base, headers=alice).get_json()["confirmations"]
    assert return_action(client, exchange["id"], bob, "accept").status_code == 200
    assert client.get(base, headers=alice).get_json()["confirmations"] == saved
    assert db.session.get(Listing, exchange["listing_id"]).status == "reserved"
    assert photo_upload(client, exchange["id"], alice, "post_return").status_code == 409
    assert return_action(client, exchange["id"], alice, "accept").get_json()["exchange"]["status"] == "completed"
    item = db.session.get(Listing, exchange["listing_id"])
    assert item.status == "available" and item.active_exchange_id is None
    detail = client.get(base, headers=alice).get_json()
    assert detail["deposit_status"]["state"] == "simulated_released"
    final = detail["confirmations"]
    for headers in (alice, bob):
        assert return_action(client, exchange["id"], headers, "accept").status_code == 200
    assert return_action(client, exchange["id"], bob, "initiate").status_code == 200
    assert client.get(base, headers=alice).get_json()["confirmations"] == final


@pytest.mark.parametrize("issuer", ["owner", "borrower"])
def test_contested_return_stays_reserved_and_never_completes(client, alice, bob, spot, issuer):
    exchange = pending_return(client, alice, bob, spot)
    assert photo_upload(client, exchange["id"], alice, "post_return").status_code == 201
    assert return_action(client, exchange["id"], bob, "accept").status_code == 200
    headers = alice if issuer == "owner" else bob
    assert return_action(client, exchange["id"], headers, "issue", reason=" ").status_code == 400
    result = return_action(client, exchange["id"], headers, "issue", reason="Garment bag is missing")
    assert result.get_json()["exchange"]["status"] == "disputed"
    assert return_action(client, exchange["id"], headers, "issue", reason="Garment bag is missing").status_code == 200
    for participant in (alice, bob):
        assert return_action(client, exchange["id"], participant, "accept").status_code == 409
        assert return_action(client, exchange["id"], participant, "initiate").status_code in (403, 409)
        assert handoff(client, exchange["id"], participant).status_code == 409
    item = db.session.get(Listing, exchange["listing_id"])
    assert item.status == "reserved" and item.active_exchange_id == exchange["id"]
    detail = client.get(f"/api/exchanges/{exchange['id']}", headers=bob).get_json()
    assert detail["exchange"]["dispute_reason"] == "Garment bag is missing"
    assert detail["deposit_status"]["state"] == "simulated_held"
    assert "no real funds" in detail["deposit_status"]["label"]


@pytest.mark.parametrize("status", ["negotiating", "cancelled", "completed", "disputed"])
def test_stage_actions_reject_invalid_states(client, alice, bob, spot, status):
    exchange = ready_exchange(client, alice, bob, spot)
    db.session.get(Exchange, exchange["id"]).status = status
    db.session.commit()
    assert handoff(client, exchange["id"], bob).status_code == 409
    for action in ("initiate", "accept", "issue"):
        assert return_action(client, exchange["id"], bob, action, reason="Missing bag").status_code == 409
    for stage in ("pre_handoff", "handoff", "pre_return", "post_return"):
        assert photo_upload(client, exchange["id"], bob, stage).status_code in (403, 409)


def test_sale_cannot_start_a_return(client, alice, bob, spot):
    exchange = reserved_exchange(client, alice, bob, spot, mode="sale")
    for action in ("initiate", "accept", "issue"):
        assert return_action(client, exchange["id"], bob, action, reason="Issue").status_code == 409
    assert photo_upload(client, exchange["id"], bob, "pre_return").status_code == 409


def test_evidence_and_confirmation_survive_a_new_app_instance(app, client, alice, bob, spot):
    from server.app import create_app

    exchange = reserved_exchange(client, alice, bob, spot)
    photo = photo_upload(client, exchange["id"], alice).get_json()["evidence"]
    assert handoff(client, exchange["id"], alice).status_code == 200
    base = f"/api/exchanges/{exchange['id']}"
    saved = client.get(base, headers=bob).get_json()["confirmations"]
    db.session.remove()
    db.engine.dispose()
    restarted = create_app(dict(app.config))
    with restarted.app_context():
        second = restarted.test_client()
        assert second.get(base, headers=bob).get_json()["confirmations"] == saved
        assert second.get(photo["url"], headers=bob).data == image_bytes()
        assert handoff(second, exchange["id"], bob).get_json()["exchange"]["status"] == "on_loan"
        assert photo_upload(second, exchange["id"], bob, "pre_return").status_code == 201
        assert return_action(second, exchange["id"], bob, "initiate").status_code == 200
        assert photo_upload(second, exchange["id"], alice, "post_return").status_code == 201
        assert return_action(second, exchange["id"], alice, "accept").status_code == 200
        saved = second.get(base, headers=bob).get_json()["confirmations"]
        db.session.remove()
        db.engine.dispose()
    restarted_again = create_app(dict(app.config))
    with restarted_again.app_context():
        third = restarted_again.test_client()
        assert third.get(base, headers=bob).get_json()["exchange"]["status"] == "return_pending"
        assert third.get(base, headers=bob).get_json()["confirmations"] == saved
        assert return_action(third, exchange["id"], bob, "accept").get_json()["exchange"]["status"] == "completed"
        assert db.session.get(Listing, exchange["listing_id"]).status == "available"
        db.session.remove()


@pytest.mark.parametrize("format_name,mime", [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")])
def test_real_supported_image_formats_decode(client, alice, bob, spot, format_name, mime):
    from PIL import Image

    output = BytesIO()
    with Image.new("RGB", (3, 3), "green") as image:
        image.save(output, format=format_name)
    exchange = reserved_exchange(client, alice, bob, spot)
    response = photo_upload(client, exchange["id"], alice, data=output.getvalue())
    assert response.status_code == 201, response.get_json()
    assert response.get_json()["evidence"]["content_type"] == mime


def test_decoded_dimensions_are_bounded_without_allocating_a_large_image(client, alice, bob, spot):
    import struct
    import zlib

    data = image_bytes()
    header = b"IHDR" + struct.pack(">IIBBBBB", 4001, 4001, 8, 2, 0, 0, 0)
    data = data[:12] + header + struct.pack(">I", zlib.crc32(header)) + data[33:]
    exchange = reserved_exchange(client, alice, bob, spot)
    response = photo_upload(client, exchange["id"], bob, data=data)
    assert response.status_code == 400
    assert "16 megapixels" in response.get_json()["error"]["message"]


def test_completion_rolls_back_if_atomic_release_fails(client, alice, bob, spot, monkeypatch):
    exchange = pending_return(client, alice, bob, spot)
    assert photo_upload(client, exchange["id"], alice, "post_return").status_code == 201
    assert return_action(client, exchange["id"], bob, "accept").status_code == 200
    monkeypatch.setattr("server.exchanges.routes.release_listing", lambda *args: False)
    response = return_action(client, exchange["id"], alice, "accept")
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "reservation_conflict"
    detail = client.get(f"/api/exchanges/{exchange['id']}", headers=bob).get_json()
    assert detail["exchange"]["status"] == "return_pending"
    returned = [record for record in detail["confirmations"] if record["stage"] == "return"]
    assert [record["participant_id"] for record in returned] == [exchange["requester_id"]]


def test_old_return_retry_cannot_release_a_new_reservation(client, alice, bob, spot):
    exchange = pending_return(client, alice, bob, spot)
    assert photo_upload(client, exchange["id"], alice, "post_return").status_code == 201
    for headers in (alice, bob):
        assert return_action(client, exchange["id"], headers, "accept").status_code == 200
    newer = ready_exchange(client, alice, bob, spot, listing_id=exchange["listing_id"])
    for headers in (alice, bob):
        assert accept(client, newer["id"], headers).status_code == 200
        assert return_action(client, exchange["id"], headers, "accept").status_code == 200
    item = db.session.get(Listing, exchange["listing_id"])
    assert item.status == "reserved" and item.active_exchange_id == newer["id"]


def test_simultaneous_pickup_confirmations_are_persisted(app, client, alice, bob, spot):
    exchange = reserved_exchange(client, alice, bob, spot)
    assert photo_upload(client, exchange["id"], alice).status_code == 201
    db.session.remove()
    barrier = Barrier(2)

    def confirm(headers):
        with app.test_client() as separate:
            barrier.wait(timeout=5)
            return handoff(separate, exchange["id"], headers).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(confirm, headers) for headers in (alice, bob)]
        assert [future.result(timeout=15) for future in futures] == [200, 200]
    detail = client.get(f"/api/exchanges/{exchange['id']}", headers=bob).get_json()
    assert detail["exchange"]["status"] == "on_loan"
    assert len(detail["confirmations"]) == 2


def test_dashboard_is_empty_without_transactions_and_requires_auth(client, bob):
    assert client.get("/api/exchanges").status_code == 401
    assert client.get("/api/exchanges", headers=bob).get_json() == {"exchanges": []}
    page = client.get("/exchanges")
    assert page.status_code == 200
    assert b"No exchanges yet" in page.data and b"Loading your exchanges" in page.data
    assert b"js/exchanges.js" in page.data and b"Stub. Person 4" not in page.data


def test_dashboard_shows_current_terms_and_private_progress(client, alice, bob, third_party, spot):
    exchange = reserved_exchange(client, alice, bob, spot)
    photo = photo_upload(client, exchange["id"], alice).get_json()["evidence"]
    assert handoff(client, exchange["id"], bob).status_code == 200
    response = client.get("/api/exchanges", headers=bob)
    assert response.headers["Cache-Control"] == "private, no-store"
    row = response.get_json()["exchanges"][0]
    assert row["status"] == "reserved"
    assert row["current_offer"]["version"] == 2
    assert row["current_offer"]["pickup_at"] == "2026-10-12T18:00:00Z"
    assert row["current_offer"]["return_deadline"] == "2026-10-15T22:00:00Z"
    assert row["pickup_meeting_spot"]["label"] == db.session.get(MeetingSpot, spot).label
    assert row["return_meeting_spot"]["id"] == spot
    assert row["participants"]["requester"]["id"] == exchange["requester_id"]
    assert row["participants"]["owner"]["badge"] == "Sandbox identity (not verified)"
    assert row["confirmations"][0]["participant_id"] == exchange["requester_id"]
    assert row["confirmations"][0]["stage"] == "handoff"
    assert row["evidence"][0]["id"] == photo["id"]
    assert "private_storage_path" not in row["evidence"][0]
    assert row["deposit_status"] == {"state": "simulated_held", "label": "Simulated: no real funds are reserved or charged."}
    assert row["my_review"] is None and row["can_review"] is False
    assert client.get("/api/exchanges", headers=third_party).get_json() == {"exchanges": []}
    # Other participants' messages and unrelated listings are never included.
    post = client.post(f"/api/exchanges/{exchange['id']}/messages", headers=alice, json={"body": "Private chat"})
    assert post.status_code == 201
    assert "Private chat" not in client.get("/api/exchanges", headers=bob).get_data(as_text=True)


def test_dashboard_preserves_unknown_meetings_and_condition(client, alice, bob):
    listing = create_listing(client, alice, condition=None, accessories=None, known_defects=None)
    exchange = start(client, listing["id"], bob)["exchange"]
    row = client.get("/api/exchanges", headers=bob).get_json()["exchanges"][0]
    assert row["id"] == exchange["id"]
    assert row["pickup_meeting_spot"] is None and row["return_meeting_spot"] is None
    assert row["current_offer"]["pickup_at"] is None
    assert row["current_offer"]["condition_snapshot"]["condition"] is None
    assert row["confirmations"] == [] and row["evidence"] == []


def test_dashboard_follows_real_loan_return_dispute_and_review_eligibility(client, alice, bob, spot):
    exchange = active_loan(client, alice, bob, spot)
    row = client.get("/api/exchanges", headers=bob).get_json()["exchanges"][0]
    assert row["status"] == "on_loan" and row["can_review"] is False
    assert photo_upload(client, exchange["id"], bob, "pre_return").status_code == 201
    assert return_action(client, exchange["id"], bob, "initiate").status_code == 200
    row = client.get("/api/exchanges", headers=alice).get_json()["exchanges"][0]
    assert row["status"] == "return_pending" and row["can_review"] is False
    assert return_action(client, exchange["id"], alice, "issue", reason="A button is missing").status_code == 200
    row = client.get("/api/exchanges", headers=bob).get_json()["exchanges"][0]
    assert row["status"] == "disputed" and row["dispute_reason"] == "A button is missing"
    assert row["can_review"] is False and row["deposit_status"]["state"] == "simulated_held"


@pytest.mark.parametrize("status", ["negotiating", "reserved"])
@pytest.mark.parametrize("actor", ["owner", "requester"])
def test_cancellation_releases_only_unused_reservation_and_is_idempotent(client, alice, bob, spot, status, actor):
    exchange = ready_exchange(client, alice, bob, spot)
    if status == "reserved":
        assert accept(client, exchange["id"], alice).status_code == 200
        assert accept(client, exchange["id"], bob).status_code == 200
    headers = alice if actor == "owner" else bob
    url = f"/api/exchanges/{exchange['id']}/cancel"
    body = {"reason": "Plans changed"}
    response = client.post(url, headers=headers, json=body)
    assert response.status_code == 200
    cancelled = response.get_json()["exchange"]
    assert cancelled["status"] == "cancelled" and cancelled["cancellation_reason"] == "Plans changed"
    assert client.post(url, headers=headers, json=body).get_json()["exchange"] == cancelled
    listing = db.session.get(Listing, exchange["listing_id"])
    assert listing.status == "available" and listing.active_exchange_id is None
    row = client.get("/api/exchanges", headers=headers).get_json()["exchanges"][0]
    assert row["deposit_status"]["state"] == "simulated_released" and row["can_review"] is False
    assert client.post(url, headers=headers, json={"reason": "Replace reason"}).status_code == 409


@pytest.mark.parametrize("reason", [None, "", " ", 42, "x" * 2001])
def test_cancellation_requires_specific_reason(client, alice, bob, spot, reason):
    exchange = reserved_exchange(client, alice, bob, spot)
    response = client.post(f"/api/exchanges/{exchange['id']}/cancel", headers=bob, json={"reason": reason})
    assert response.status_code == 400
    assert db.session.get(Exchange, exchange["id"]).status == "reserved"
    assert db.session.get(Listing, exchange["listing_id"]).active_exchange_id == exchange["id"]


@pytest.mark.parametrize("status", ["on_loan", "return_pending", "completed", "disputed"])
def test_cancellation_cannot_skip_later_stages(client, alice, bob, spot, status):
    exchange = reserved_exchange(client, alice, bob, spot)
    db.session.get(Exchange, exchange["id"]).status = status
    db.session.commit()
    response = client.post(f"/api/exchanges/{exchange['id']}/cancel", headers=bob, json={"reason": "Plans changed"})
    assert response.status_code == 409
    assert db.session.get(Exchange, exchange["id"]).status == status
    assert db.session.get(Listing, exchange["listing_id"]).active_exchange_id == exchange["id"]


def test_cancellation_is_blocked_after_first_pickup_confirmation(client, alice, bob, spot):
    exchange = reserved_exchange(client, alice, bob, spot)
    assert photo_upload(client, exchange["id"], bob).status_code == 201
    assert handoff(client, exchange["id"], bob).status_code == 200
    response = client.post(f"/api/exchanges/{exchange['id']}/cancel", headers=alice, json={"reason": "Changed mind"})
    assert response.status_code == 409
    assert db.session.get(Listing, exchange["listing_id"]).status == "reserved"


def test_failed_cancellation_release_rolls_back(client, alice, bob, spot, monkeypatch):
    exchange = reserved_exchange(client, alice, bob, spot)
    monkeypatch.setattr("server.exchanges.routes.release_listing", lambda *args: False)
    response = client.post(f"/api/exchanges/{exchange['id']}/cancel", headers=bob, json={"reason": "Plans changed"})
    assert response.status_code == 409
    saved = db.session.get(Exchange, exchange["id"])
    assert saved.status == "reserved" and saved.cancellation_reason is None


def test_old_cancellation_does_not_release_a_new_reservation(client, alice, bob, spot):
    exchange = reserved_exchange(client, alice, bob, spot)
    url = f"/api/exchanges/{exchange['id']}/cancel"
    body = {"reason": "Plans changed"}
    assert client.post(url, headers=bob, json=body).status_code == 200
    newer = ready_exchange(client, alice, bob, spot, listing_id=exchange["listing_id"])
    assert accept(client, newer["id"], alice).status_code == 200
    assert accept(client, newer["id"], bob).status_code == 200
    assert client.post(url, headers=bob, json=body).status_code == 200
    assert db.session.get(Listing, exchange["listing_id"]).active_exchange_id == newer["id"]


@pytest.mark.parametrize("actor", ["owner", "requester"])
def test_standalone_dispute_matches_return_issue_and_never_charges(client, alice, bob, spot, actor):
    exchange = pending_return(client, alice, bob, spot)
    headers = alice if actor == "owner" else bob
    url = f"/api/exchanges/{exchange['id']}/dispute"
    reason = "The agreed accessory is missing"
    response = client.post(url, headers=headers, json={"reason": reason})
    assert response.status_code == 200
    disputed = response.get_json()["exchange"]
    assert disputed["status"] == "disputed" and disputed["dispute_reason"] == reason
    assert client.post(url, headers=headers, json={"reason": reason}).get_json()["exchange"] == disputed
    assert return_action(client, exchange["id"], headers, "issue", reason=reason).get_json()["exchange"] == disputed
    detail = client.get(f"/api/exchanges/{exchange['id']}", headers=headers).get_json()
    assert detail["deposit_status"] == {"state": "simulated_held", "label": "Simulated: no real funds are reserved or charged."}
    assert db.session.get(Listing, exchange["listing_id"]).active_exchange_id == exchange["id"]
    assert return_action(client, exchange["id"], headers, "accept").status_code == 409


@pytest.mark.parametrize("status", ["negotiating", "reserved", "on_loan", "completed", "cancelled"])
def test_standalone_dispute_rejects_invalid_states(client, alice, bob, spot, status):
    exchange = ready_exchange(client, alice, bob, spot)
    db.session.get(Exchange, exchange["id"]).status = status
    db.session.commit()
    assert client.post(f"/api/exchanges/{exchange['id']}/dispute", headers=bob,
                       json={"reason": "Specific issue"}).status_code == 409
    assert db.session.get(Exchange, exchange["id"]).status == status


def test_sale_cannot_use_standalone_return_dispute(client, alice, bob, spot):
    exchange = ready_exchange(client, alice, bob, spot, mode="sale")
    assert client.post(f"/api/exchanges/{exchange['id']}/dispute", headers=bob,
                       json={"reason": "Specific issue"}).status_code == 409
