"""Listings: create/read, ownership enforcement with two users, money validation, photos."""

import io

from tests.conftest import ALICE, BOB, create_listing

PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_create_requires_verified_user(client):
    resp = client.post("/api/listings", json={"title": "x"})
    assert resp.status_code == 401


def test_wrong_domain_cannot_create(client, mallory):
    resp = client.post("/api/listings", json={"title": "x"}, headers=mallory)
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "domain_not_allowed"


def test_create_and_read_listing(client, alice):
    listing = create_listing(client, alice)
    me = client.get("/api/me", headers=alice).get_json()["profile"]
    assert listing["owner_id"] == me["id"]
    assert listing["status"] == "available"
    assert listing["sale_price_cents"] == 9000
    assert listing["created_at"].endswith("Z")

    public = client.get(f"/api/listings/{listing['id']}")
    assert public.status_code == 200
    body = public.get_json()["listing"]
    assert body["title"] == "Navy suit 40R"
    assert body["owner"]["display_name"] == me["display_name"]
    assert "email" not in body["owner"]
    assert ALICE not in public.get_data(as_text=True)

    feed = client.get("/api/listings").get_json()["listings"]
    assert [l["id"] for l in feed] == [listing["id"]]


def test_client_supplied_owner_id_is_ignored(client, alice, bob):
    bob_id = client.get("/api/me", headers=bob).get_json()["profile"]["id"]
    listing = create_listing(client, alice, owner_id=bob_id, status="sold")
    alice_id = client.get("/api/me", headers=alice).get_json()["profile"]["id"]
    assert listing["owner_id"] == alice_id
    assert listing["status"] == "available"


def test_second_user_cannot_edit_someone_elses_listing(client, alice, bob):
    listing = create_listing(client, alice)
    url = f"/api/listings/{listing['id']}"

    as_owner = client.patch(url, json={"title": "Navy suit 40R (updated)"}, headers=alice)
    assert as_owner.status_code == 200
    assert as_owner.get_json()["listing"]["title"] == "Navy suit 40R (updated)"

    as_bob = client.patch(url, json={"title": "hijacked"}, headers=bob)
    assert as_bob.status_code == 403
    assert as_bob.get_json()["error"]["code"] == "forbidden"

    anonymous = client.patch(url, json={"title": "hijacked"})
    assert anonymous.status_code == 401

    final = client.get(url).get_json()["listing"]
    assert final["title"] == "Navy suit 40R (updated)"


def test_money_validation(client, alice):
    negative = client.post("/api/listings", json={**_base(), "sale_price_cents": -1}, headers=alice)
    assert negative.status_code == 400
    assert "sale_price_cents" in negative.get_json()["error"]["fields"]

    fractional = client.post("/api/listings", json={**_base(), "sale_price_cents": 12.5}, headers=alice)
    assert fractional.status_code == 400
    assert "sale_price_cents" in fractional.get_json()["error"]["fields"]

    boolean = client.post("/api/listings", json={**_base(), "rental_fee_cents": True}, headers=alice)
    assert boolean.status_code == 400

    percent = client.post("/api/listings", json={**_base(), "collateral_percent": 150}, headers=alice)
    assert percent.status_code == 400
    assert "collateral_percent" in percent.get_json()["error"]["fields"]


def test_mode_requires_matching_price_fields(client, alice):
    body = {**_base(), "allowed_modes": ["sale"], "sale_price_cents": None}
    resp = client.post("/api/listings", json=body, headers=alice)
    assert resp.status_code == 400
    assert "sale_price_cents" in resp.get_json()["error"]["fields"]

    body = {**_base(), "allowed_modes": ["borrow"], "proposed_item_value_cents": None}
    resp = client.post("/api/listings", json=body, headers=alice)
    assert resp.status_code == 400
    assert "proposed_item_value_cents" in resp.get_json()["error"]["fields"]


def test_borrow_defaults_to_full_collateral_and_explicit_free_loan(client, alice):
    body = {**_base(), "allowed_modes": ["borrow"], "proposed_item_value_cents": 5000}
    body.pop("rental_fee_cents", None)
    body.pop("collateral_percent", None)
    listing = client.post("/api/listings", json=body, headers=alice).get_json()["listing"]
    assert listing["rental_fee_cents"] == 0
    assert listing["collateral_percent"] == 100


def test_unknown_mode_rejected(client, alice):
    resp = client.post("/api/listings", json={**_base(), "allowed_modes": ["trade"]}, headers=alice)
    assert resp.status_code == 400
    assert "allowed_modes" in resp.get_json()["error"]["fields"]


def test_photo_upload_owner_only_and_validates_magic_bytes(client, alice, bob):
    listing = create_listing(client, alice)
    url = f"/api/listings/{listing['id']}/photo"

    fake = client.post(
        url,
        data={"photo": (io.BytesIO(b"MZ\x90\x00 definitely not an image"), "photo.png")},
        content_type="multipart/form-data",
        headers=alice,
    )
    assert fake.status_code == 400
    assert fake.get_json()["error"]["code"] == "unsupported_image"

    as_bob = client.post(
        url, data={"photo": (io.BytesIO(PNG_1x1), "a.png")}, content_type="multipart/form-data", headers=bob
    )
    assert as_bob.status_code == 403

    ok = client.post(
        url,
        data={"photo": (io.BytesIO(PNG_1x1), "../../evil.png")},
        content_type="multipart/form-data",
        headers=alice,
    )
    assert ok.status_code == 200, ok.get_json()
    photo_url = ok.get_json()["listing"]["public_photo_url"]
    assert photo_url.startswith("/media/public/")
    assert "evil" not in photo_url
    served = client.get(photo_url)
    assert served.status_code == 200
    assert served.data == PNG_1x1


def test_media_path_traversal_refused(client):
    resp = client.get("/media/public/../../requirements.txt")
    assert resp.status_code == 404


def test_meeting_spots_public(client):
    resp = client.get("/api/meeting-spots")
    assert resp.status_code == 200
    assert resp.get_json() == {"meeting_spots": []}


def test_listing_rejects_unknown_meeting_spot(client, alice):
    resp = client.post("/api/listings", json={**_base(), "meeting_spot_ids": ["nope"]}, headers=alice)
    assert resp.status_code == 400
    assert "meeting_spot_ids" in resp.get_json()["error"]["fields"]


def _base():
    from tests.conftest import LISTING_BODY

    return dict(LISTING_BODY)
