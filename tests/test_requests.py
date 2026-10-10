"""Need requests: ownership, sanitized public views, normalization, and matching."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.conftest import create_listing

REQUEST_BODY = {
    "original_text": "I need a navy suit, 40R, for an interview next Tuesday. Would rather borrow.",
    "normalized": {
        "category": "formalwear",
        "required_specifications": {"jacket_size": "40R"},
        "preferred_specifications": {"color": "navy"},
    },
    "modes": ["borrow", "sale"],
    "budget_cents": 4000,
    "max_deposit_cents": 8000,
    "needed_by": "2026-10-14T13:00:00Z",
    "use_start": "2026-10-13T16:00:00Z",
    "use_end": "2026-10-15T22:00:00Z",
    "pickup_windows": [{"start": "2026-10-13T18:00:00Z", "end": "2026-10-13T20:00:00Z"}],
    "area": "Central campus",
}


def _create(client, headers, **overrides):
    resp = client.post("/api/requests", json={**REQUEST_BODY, **overrides}, headers=headers)
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["request"]


def test_create_requires_verified_user(client):
    assert client.post("/api/requests", json=REQUEST_BODY).status_code == 401


def test_create_and_owner_read(client, alice):
    req = _create(client, alice)
    assert req["status"] == "draft"
    assert req["visibility"] == "private"
    assert req["needed_by"] == "2026-10-14T13:00:00Z"
    assert req["pickup_windows"][0]["start"] == "2026-10-13T18:00:00Z"
    resp = client.get(f"/api/requests/{req['id']}", headers=alice)
    assert resp.status_code == 200
    assert resp.get_json()["view"] == "owner"
    assert resp.get_json()["request"]["original_text"] == REQUEST_BODY["original_text"]


def test_naive_timestamp_rejected(client, alice):
    resp = client.post("/api/requests", json={**REQUEST_BODY, "needed_by": "2026-10-14T13:00:00"}, headers=alice)
    assert resp.status_code == 400
    assert "needed_by" in resp.get_json()["error"]["fields"]


def test_offset_timestamp_is_stored_as_utc(client, alice):
    req = _create(client, alice, needed_by="2026-10-14T09:00:00-04:00")
    assert req["needed_by"] == "2026-10-14T13:00:00Z"


def test_private_request_hidden_from_others(client, alice, bob):
    req = _create(client, alice)
    assert client.get(f"/api/requests/{req['id']}", headers=bob).status_code == 404
    assert client.get(f"/api/requests/{req['id']}").status_code == 404
    assert client.get("/api/requests").get_json()["requests"] == []


def test_publish_is_owner_only_and_sanitizes(client, alice, bob):
    req = _create(client, alice)
    url = f"/api/requests/{req['id']}/publish"
    assert client.post(url, headers=bob).status_code == 403
    assert client.post(url).status_code == 401

    resp = client.post(url, headers=alice)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["request"]["visibility"] == "public"
    assert body["request"]["status"] == "open"
    preview = body["public_preview"]
    assert "pickup_windows" not in preview
    assert "original_text" not in preview
    assert "use_start" not in preview
    assert preview["needed_by_date"] == "2026-10-14"
    assert preview["area"] == "Central campus"
    assert preview["requester"]["display_name"]
    assert "email" not in preview["requester"]

    as_bob = client.get(f"/api/requests/{req['id']}", headers=bob).get_json()
    assert as_bob["view"] == "public"
    assert "pickup_windows" not in as_bob["request"]

    feed = client.get("/api/requests").get_json()
    assert feed["view"] == "public"
    assert [r["id"] for r in feed["requests"]] == [req["id"]]
    assert "pickup_windows" not in feed["requests"][0]


def test_mine_lists_only_my_requests(client, alice, bob):
    mine = _create(client, alice)
    _create(client, bob)
    resp = client.get("/api/requests?mine=1", headers=alice).get_json()
    assert resp["view"] == "owner"
    assert [r["id"] for r in resp["requests"]] == [mine["id"]]
    assert client.get("/api/requests?mine=1").status_code == 401


def test_update_owner_only(client, alice, bob):
    req = _create(client, alice)
    url = f"/api/requests/{req['id']}"
    assert client.patch(url, json={"area": "South campus"}, headers=bob).status_code == 403
    ok = client.patch(url, json={"area": "South campus", "budget_cents": 5000}, headers=alice)
    assert ok.status_code == 200
    assert ok.get_json()["request"]["area"] == "South campus"
    assert ok.get_json()["request"]["budget_cents"] == 5000
    cancelled = client.patch(url, json={"status": "cancelled"}, headers=alice)
    assert cancelled.get_json()["request"]["status"] == "cancelled"
    assert client.patch(url, json={"area": "x"}, headers=alice).status_code == 409


def test_normalize_manual_fallback_is_editable_and_invents_nothing(client, alice, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    resp = client.post("/api/requests/normalize", json={"text": "I need a suit"}, headers=alice)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["fixture"] is False
    normalized = body["normalized"]
    assert normalized["source"] == "manual"
    assert normalized["original_text"] == "I need a suit"
    assert normalized["required_specifications"] == {}
    assert normalized["preferred_specifications"] == {}
    for field in ("modes", "category", "budget_cents", "max_deposit_cents", "needed_by", "use_start", "use_end", "area"):
        assert normalized[field] is None
    assert normalized["ambiguous_dates"] == []
    assert any("Fill in" in question for question in normalized["follow_up_questions"])
    assert client.post("/api/requests/normalize", json={"text": "I need a suit"}).status_code == 401
    assert client.post("/api/requests/normalize", json={"text": ""}, headers=alice).status_code == 400


def test_validated_gemini_proposal_flows_into_request_and_catalog_match(client, alice, bob, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "mock-only-key")
    sdk_client = MagicMock()
    sdk_client.__enter__.return_value = sdk_client
    sdk_client.models.generate_content.return_value = SimpleNamespace(text=json.dumps({
        "modes": ["borrow"], "category": "formalwear",
        "required_specifications": [{"name": "jacket_size", "value": "40R"}],
        "preferred_specifications": [{"name": "color", "value": "navy"}],
        "budget_dollars": "20", "max_deposit_dollars": "60",
        "needed_by": None, "use_start": None, "use_end": None, "area": None,
        "ambiguous_dates": [], "follow_up_questions": [],
    }))
    monkeypatch.setattr("server.intelligence.normalize.genai.Client", lambda **_kwargs: sdk_client)

    text = "Borrow a navy 40R suit; fee under $20, deposit up to $60."
    proposed = client.post("/api/requests/normalize", json={"text": text}, headers=alice)
    assert proposed.status_code == 200
    assert proposed.get_json()["fixture"] is False
    normalized = proposed.get_json()["normalized"]
    assert normalized["source"] == "gemini"
    assert normalized["required_specifications"] == {"jacket_size": "40R"}
    assert normalized["budget_cents"] == 2000
    assert normalized["max_deposit_cents"] == 6000

    listing = create_listing(client, bob, collateral_percent=30)
    created = client.post("/api/requests", json={
        "original_text": text, "normalized": normalized,
        "modes": normalized["modes"], "budget_cents": normalized["budget_cents"],
        "max_deposit_cents": normalized["max_deposit_cents"],
    }, headers=alice)
    assert created.status_code == 201
    need = created.get_json()["request"]
    assert need["normalized"] == normalized
    assert need["visibility"] == "private"
    assert client.get(f"/api/requests/{need['id']}", headers=bob).status_code == 404
    matches = client.get(f"/api/requests/{need['id']}/matches", headers=alice).get_json()
    assert matches["source"] == "deterministic"
    assert [entry["listing_id"] for entry in matches["confirmed"]] == [listing["id"]]


def test_matches_are_deterministic_and_reference_real_listings_only(client, alice, bob):
    listing = create_listing(client, bob)
    wrong_size = create_listing(client, bob, title="Wrong size suit", specifications={"jacket_size": "42R", "color": "navy"})
    own_listing = create_listing(client, alice, title="my own thing")
    req = _create(client, alice)
    url = f"/api/requests/{req['id']}/matches"
    assert client.get(url, headers=bob).status_code == 403
    assert client.get(url).status_code == 401
    resp = client.get(url, headers=alice)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["source"] == "deterministic"
    assert body["fixture"] is False
    assert body["confirmed"] == []
    assert [m["listing_id"] for m in body["needs_confirmation"]] == [listing["id"]]
    assert [m["listing_id"] for m in body["rejected"]] == [wrong_size["id"]]
    ids = {entry["listing_id"] for bucket in ("confirmed", "needs_confirmation", "rejected") for entry in body[bucket]}
    assert own_listing["id"] not in ids
    entry = body["needs_confirmation"][0]
    assert entry["mode"] == "borrow"
    assert set(entry["unknown_required"]) == {"deposit_agreement", "availability"}
    assert any("jacket_size matches" in reason for reason in entry["reasons"])
    assert any("deposit negotiation required" in shortcoming for shortcoming in entry["shortcomings"])
    assert entry["listing"]["title"] == listing["title"]
    assert any("jacket_size mismatch" in shortcoming for shortcoming in body["rejected"][0]["shortcomings"])
