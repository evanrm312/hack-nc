"""Service listings and their separate schedule/confirmation path."""

from flask_migrate import upgrade
from pydantic import ValidationError
import pytest
from sqlalchemy import inspect, text

from server.app import create_app
from server.db import db
from server.intelligence.normalize import Extraction, _to_request
from server.models import NeedRequest
from tests.conftest import auth, create_listing, publish_listing


WINDOW = {"start": "2030-10-12T12:00:00Z", "end": "2030-10-12T14:00:00Z"}
LISTING = {
    "title": "Calculus tutoring",
    "description": "One-on-one calculus help at the library.",
    "category": "tutoring",
    "allowed_modes": ["service"],
    "service_price_cents": 2500,
    "service_duration_minutes": 60,
    "service_available_windows": [WINDOW],
}
REQUEST = {
    "original_text": "I need an hour of calculus tutoring.",
    "normalized": {"source": "manual", "category": "tutoring",
                   "required_specifications": {}, "preferred_specifications": {}},
    "modes": ["service"],
    "budget_cents": 3000,
    "service_duration_minutes": 60,
    "service_time_windows": [WINDOW],
}


def service_listing(client, alice):
    response = client.post("/api/listings", json=LISTING, headers=alice)
    assert response.status_code == 201, response.get_json()
    return publish_listing(client, alice, response.get_json()["listing"])


def exchange_with_offer(client, alice, bob):
    listing = service_listing(client, alice)
    created = client.post("/api/exchanges", json={"listing_id": listing["id"], "mode": "service"}, headers=bob)
    assert created.status_code == 201, created.get_json()
    exchange = created.get_json()["exchange"]
    offered = client.post(f"/api/exchanges/{exchange['id']}/offers", json={
        "service_price_cents": 2500, "service_duration_minutes": 60,
        "service_scheduled_at": WINDOW["start"],
    }, headers=alice)
    assert offered.status_code == 201, offered.get_json()
    return listing, exchange, offered.get_json()["offer"]


def test_service_listing_has_only_service_terms_and_limited_category(client, alice):
    listing = service_listing(client, alice)
    assert listing["allowed_modes"] == ["service"]
    assert listing["service_price_cents"] == 2500
    assert listing["service_duration_minutes"] == 60
    assert listing["service_available_windows"] == [WINDOW]
    for forbidden in ("condition", "collateral_percent", "proposed_item_value_cents",
                      "rental_fee_cents", "sale_price_cents"):
        assert forbidden not in listing
    assert [row["id"] for row in client.get("/api/listings?mode=service").get_json()["listings"]] == [listing["id"]]
    for change, field in [
        ({"category": "electronics"}, "category"),
        ({"allowed_modes": ["sale", "service"]}, "allowed_modes"),
        ({"collateral_percent": 0}, "collateral_percent"),
        ({"deposit_cents": 0}, "deposit_cents"),
        ({"agreed_item_value_cents": 10000}, "agreed_item_value_cents"),
        ({"proposed_item_value_cents": 10000}, "proposed_item_value_cents"),
        ({"condition": "good"}, "condition"),
        ({"service_duration_minutes": 0}, "service_duration_minutes"),
        ({"service_available_windows": []}, "service_available_windows"),
        ({"service_available_windows": [{"start": "2030-10-12T12:00:00Z",
                                          "end": "2030-10-12T12:30:00Z"}]}, "service_available_windows"),
    ]:
        response = client.post("/api/listings", json={**LISTING, **change}, headers=alice)
        assert response.status_code == 400
        assert field in response.get_json()["error"]["fields"]


def test_service_request_matches_without_deposit(client, alice, bob):
    listing = service_listing(client, alice)
    response = client.post("/api/requests", json=REQUEST, headers=bob)
    assert response.status_code == 201, response.get_json()
    need = response.get_json()["request"]
    assert need["modes"] == ["service"]
    assert "max_deposit_cents" not in need
    matches = client.get(f"/api/requests/{need['id']}/matches", headers=bob)
    assert matches.status_code == 200, matches.get_json()
    assert [entry["listing_id"] for entry in matches.get_json()["confirmed"]] == [listing["id"]]
    assert matches.get_json()["confirmed"][0]["mode"] == "service"
    bad = client.post("/api/requests", json={**REQUEST, "max_deposit_cents": 0}, headers=bob)
    assert bad.status_code == 400
    assert "max_deposit_cents" in bad.get_json()["error"]["fields"]
    deposit = client.post("/api/requests", json={**REQUEST, "deposit_cents": 0}, headers=bob)
    assert deposit.status_code == 400
    assert "deposit_cents" in deposit.get_json()["error"]["fields"]
    combined = client.post("/api/requests", json={**REQUEST, "modes": ["sale", "service"]}, headers=bob)
    assert combined.status_code == 400
    assert "modes" in combined.get_json()["error"]["fields"]


def test_normalization_can_propose_service_without_deposit():
    data = {"modes": ["service"], "category": "tutoring",
            "required_specifications": [], "preferred_specifications": [],
            "budget_dollars": "30", "max_deposit_dollars": None,
            "needed_by": None, "use_start": None, "use_end": None,
            "area": None, "ambiguous_dates": [], "follow_up_questions": []}
    result = _to_request(Extraction.model_validate(data), "I need tutoring")
    assert result["modes"] == ["service"]
    assert result["budget_cents"] == 3000
    assert result["max_deposit_cents"] is None
    assert any("service" in question for question in result["follow_up_questions"])
    with pytest.raises(ValidationError):
        Extraction.model_validate({**data, "max_deposit_dollars": "0"})


def test_service_offer_rejects_deposit_and_item_terms(client, alice, bob):
    listing, exchange, offer = exchange_with_offer(client, alice, bob)
    assert offer["service_price_cents"] == 2500
    assert "deposit_cents" not in offer
    assert "agreed_item_value_cents" not in offer
    create_with_deposit = client.post("/api/exchanges", json={
        "listing_id": listing["id"], "mode": "service", "deposit_cents": 0,
    }, headers=bob)
    assert create_with_deposit.status_code == 400
    outside_window = client.post(f"/api/exchanges/{exchange['id']}/offers", json={
        "service_price_cents": 2500, "service_duration_minutes": 60,
        "service_scheduled_at": "2030-10-12T13:30:00Z",
    }, headers=alice)
    assert outside_window.status_code == 400
    for field, value in [("deposit_cents", 0), ("collateral_percent", 0),
                         ("agreed_item_value_cents", 10000), ("condition", "good"),
                         ("condition_snapshot", {"condition": "good"}),
                         ("pickup_meeting_spot_id", "spot"), ("pickup_at", WINDOW["start"]),
                         ("return_meeting_spot_id", "spot"), ("return_deadline", WINDOW["end"]),
                         ("handoff", True), ("evidence", []), ("return", True)]:
        created = client.post("/api/exchanges", json={
            "listing_id": listing["id"], "mode": "service", field: value,
        }, headers=bob)
        assert created.status_code == 400
        assert field in created.get_json()["error"]["fields"]
        response = client.post(f"/api/exchanges/{exchange['id']}/offers", json={
            "service_price_cents": 2500, "service_duration_minutes": 60,
            "service_scheduled_at": WINDOW["start"], field: value,
        }, headers=bob)
        assert response.status_code == 400
        assert field in response.get_json()["error"]["fields"]
    rejected = client.post(f"/api/exchanges/{exchange['id']}/accept", json={
        "version": 1, "deposit_cents": 0,
    }, headers=bob)
    assert rejected.status_code == 400
    assert "deposit_cents" in rejected.get_json()["error"]["fields"]


@pytest.mark.parametrize("status,expected", [
    ("draft", 201), ("open", 201), ("fulfilled", 409),
    ("cancelled", 409), ("expired", 409),
])
def test_service_source_request_must_be_eligible(client, app, alice, bob, status, expected):
    listing = service_listing(client, alice)
    source = client.post("/api/requests", json=REQUEST, headers=bob).get_json()["request"]
    need = db.session.get(NeedRequest, source["id"])
    need.status = status
    db.session.commit()
    response = client.post("/api/exchanges", json={
        "listing_id": listing["id"], "mode": "service", "source_request_id": source["id"],
    }, headers=bob)
    assert response.status_code == expected
    if expected == 409:
        assert response.get_json()["error"]["code"] == "request_closed"


def test_service_source_request_must_include_service_mode(client, alice, bob):
    listing = service_listing(client, alice)
    source = client.post("/api/requests", json={
        "original_text": "Need an item", "modes": ["sale"],
    }, headers=bob).get_json()["request"]
    response = client.post("/api/exchanges", json={
        "listing_id": listing["id"], "mode": "service", "source_request_id": source["id"],
    }, headers=bob)
    assert response.status_code == 400
    assert "source_request_id" in response.get_json()["error"]["fields"]


def test_exchange_list_includes_all_modes_and_complete_is_service_only(client, app, alice, bob):
    app.config["SANDBOX_USERS"].append("charlie@unc.edu")
    item = create_listing(client, alice)
    service = service_listing(client, alice)
    created = []
    for listing, mode in ((item, "sale"), (item, "borrow"), (service, "service")):
        response = client.post("/api/exchanges", json={
            "listing_id": listing["id"], "mode": mode,
        }, headers=bob)
        assert response.status_code == 201, response.get_json()
        created.append(response.get_json()["exchange"])
    listed = client.get("/api/exchanges", headers=bob)
    assert listed.status_code == 200
    assert {row["id"] for row in listed.get_json()["exchanges"]} == {row["id"] for row in created}
    assert {row["mode"] for row in listed.get_json()["exchanges"]} == {"sale", "borrow", "service"}
    assert listed.headers["Cache-Control"] == "private, no-store"
    assert listed.headers["X-Content-Type-Options"] == "nosniff"
    assert client.get("/api/exchanges", headers=auth("charlie@unc.edu")).get_json() == {"exchanges": []}
    for exchange in created[:2]:
        response = client.post(f"/api/exchanges/{exchange['id']}/complete",
                               json={"confirm": True}, headers=bob)
        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "invalid_transition"


def test_service_schedules_then_both_confirm_without_loan_or_return(client, alice, bob):
    listing, exchange, offer = exchange_with_offer(client, alice, bob)
    base = f"/api/exchanges/{exchange['id']}"
    first = client.post(base + "/accept", json={"version": 1}, headers=alice)
    assert first.status_code == 200
    assert first.get_json()["exchange"]["status"] == "negotiating"
    assert client.post(base + "/complete", json={"confirm": True}, headers=alice).status_code == 409
    second = client.post(base + "/accept", json={"version": 1}, headers=bob)
    assert second.status_code == 200, second.get_json()
    assert second.get_json()["exchange"]["status"] == "scheduled"
    assert "no real funds" in second.get_json()["exchange"]["payment_notice"]
    assert client.get(f"/api/listings/{listing['id']}").get_json()["listing"]["status"] == "reserved"
    for step in ("handoff", "return", "evidence"):
        response = client.post(base + "/" + step, json={"action": "initiate"}, headers=bob)
        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "invalid_transition"
    assert client.get(base + "/evidence", headers=alice).status_code == 409
    first_confirmation = client.post(base + "/complete", json={"confirm": True}, headers=alice)
    assert first_confirmation.get_json()["exchange"]["status"] == "scheduled"
    completed = client.post(base + "/complete", json={"confirm": True}, headers=bob)
    assert completed.status_code == 200
    assert completed.get_json()["exchange"]["status"] == "completed"
    assert client.get(f"/api/listings/{listing['id']}").get_json()["listing"]["status"] == "available"
    assert client.post(base + "/return", json={"action": "initiate"}, headers=bob).status_code == 409


def test_service_permissions_revisions_cancel_and_dispute(client, app, alice, bob):
    app.config["SANDBOX_USERS"].append("charlie@unc.edu")
    charlie = auth("charlie@unc.edu")
    listing, exchange, _ = exchange_with_offer(client, alice, bob)
    base = f"/api/exchanges/{exchange['id']}"
    assert client.get(base, headers=charlie).status_code == 403
    assert client.post(base + "/accept", json={"version": 1}, headers=charlie).status_code == 403
    assert client.get(base + "/messages", headers=charlie).status_code == 403
    for action in ("complete", "cancel", "dispute", "handoff", "return", "evidence"):
        assert client.post(base + "/" + action, json={}, headers=charlie).status_code == 403
    client.post(base + "/accept", json={"version": 1}, headers=alice)
    revised = client.post(base + "/offers", json={
        "service_price_cents": 2000, "service_duration_minutes": 60,
        "service_scheduled_at": "2030-10-12T13:00:00Z",
    }, headers=bob)
    assert revised.status_code == 201, revised.get_json()
    assert revised.get_json()["offer"]["version"] == 2
    assert revised.get_json()["offer"]["owner_accepted_at"] is None
    assert revised.get_json()["offer"]["requester_accepted_at"] is None
    assert client.post(base + "/accept", json={"version": 1}, headers=bob).status_code == 409
    client.post(base + "/accept", json={"version": 2}, headers=alice)
    client.post(base + "/accept", json={"version": 2}, headers=bob)
    disputed = client.post(base + "/dispute", json={"reason": "Session did not happen"}, headers=bob)
    assert disputed.status_code == 200
    assert disputed.get_json()["exchange"]["status"] == "disputed"
    assert client.post(base + "/complete", json={"confirm": True}, headers=alice).status_code == 409
    assert client.get(f"/api/listings/{listing['id']}").get_json()["listing"]["status"] == "available"
    another, exchange2, _ = exchange_with_offer(client, alice, bob)
    cancelled = client.post(f"/api/exchanges/{exchange2['id']}/cancel", json={"reason": "Plans changed"}, headers=alice)
    assert cancelled.get_json()["exchange"]["status"] == "cancelled"
    assert client.post(f"/api/exchanges/{exchange2['id']}/accept", json={"version": 1}, headers=bob).status_code == 409


def test_service_cancel_and_dispute_state_limits(client, alice, bob):
    listing, exchange, _ = exchange_with_offer(client, alice, bob)
    base = f"/api/exchanges/{exchange['id']}"
    assert client.post(base + "/dispute", json={"reason": "Too early"}, headers=bob).status_code == 409
    for headers in (alice, bob):
        assert client.post(base + "/accept", json={"version": 1}, headers=headers).status_code == 200
    cancelled = client.post(base + "/cancel", json={"reason": "Plans changed"}, headers=bob)
    assert cancelled.status_code == 200
    assert cancelled.get_json()["exchange"]["status"] == "cancelled"
    assert client.get(f"/api/listings/{listing['id']}").get_json()["listing"]["status"] == "available"
    assert client.post(base + "/dispute", json={"reason": "Too late"}, headers=alice).status_code == 409

    _, completed_exchange, _ = exchange_with_offer(client, alice, bob)
    completed_base = f"/api/exchanges/{completed_exchange['id']}"
    for headers in (alice, bob):
        assert client.post(completed_base + "/accept", json={"version": 1}, headers=headers).status_code == 200
    for headers in (alice, bob):
        assert client.post(completed_base + "/complete", json={"confirm": True}, headers=headers).status_code == 200
    assert client.post(completed_base + "/cancel", json={"reason": "Too late"}, headers=alice).status_code == 409
    disputed = client.post(completed_base + "/dispute", json={"reason": "Service concern"}, headers=bob)
    assert disputed.status_code == 200
    assert disputed.get_json()["exchange"]["status"] == "disputed"


def test_only_one_service_exchange_can_schedule_a_listing(client, alice, bob):
    listing = service_listing(client, alice)
    exchanges = []
    for _ in range(2):
        created = client.post("/api/exchanges", json={"listing_id": listing["id"], "mode": "service"}, headers=bob)
        exchange_id = created.get_json()["exchange"]["id"]
        offered = client.post(f"/api/exchanges/{exchange_id}/offers", json={
            "service_price_cents": 2500, "service_duration_minutes": 60,
            "service_scheduled_at": WINDOW["start"],
        }, headers=alice)
        assert offered.status_code == 201
        exchanges.append(exchange_id)
    for exchange_id in exchanges:
        assert client.post(f"/api/exchanges/{exchange_id}/accept", json={"version": 1}, headers=alice).status_code == 200
    assert client.post(f"/api/exchanges/{exchanges[0]}/accept", json={"version": 1}, headers=bob).status_code == 200
    conflict = client.post(f"/api/exchanges/{exchanges[1]}/accept", json={"version": 1}, headers=bob)
    assert conflict.status_code == 409
    assert conflict.get_json()["error"]["code"] == "reservation_conflict"
    assert client.get(f"/api/exchanges/{exchanges[1]}", headers=bob).get_json()["exchange"]["status"] == "negotiating"


def test_service_listing_allows_only_one_active_booking_even_at_different_times(client, alice, bob):
    later = {"start": "2030-10-13T12:00:00Z", "end": "2030-10-13T14:00:00Z"}
    response = client.post("/api/listings", json={
        **LISTING, "service_available_windows": [WINDOW, later],
    }, headers=alice)
    assert response.status_code == 201, response.get_json()
    listing_id = publish_listing(client, alice, response.get_json()["listing"])["id"]
    exchanges = []
    for window in (WINDOW, later):
        created = client.post("/api/exchanges", json={
            "listing_id": listing_id, "mode": "service",
        }, headers=bob)
        assert created.status_code == 201
        exchange_id = created.get_json()["exchange"]["id"]
        offered = client.post(f"/api/exchanges/{exchange_id}/offers", json={
            "service_price_cents": 2500, "service_duration_minutes": 60,
            "service_scheduled_at": window["start"],
        }, headers=alice)
        assert offered.status_code == 201
        exchanges.append(exchange_id)
    for exchange_id in exchanges:
        assert client.post(f"/api/exchanges/{exchange_id}/accept",
                           json={"version": 1}, headers=alice).status_code == 200
    assert client.post(f"/api/exchanges/{exchanges[0]}/accept",
                       json={"version": 1}, headers=bob).status_code == 200
    blocked = client.post(f"/api/exchanges/{exchanges[1]}/accept",
                          json={"version": 1}, headers=bob)
    assert blocked.status_code == 409
    assert blocked.get_json()["error"]["code"] == "reservation_conflict"


def test_migration_adds_service_fields_to_existing_database(tmp_path):
    config = {"TESTING": True, "APP_ENV": "development",
              "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'service_migration.sqlite'}",
              "AUTH_MODE": "sandbox", "SANDBOX_USERS": ["alice@unc.edu"],
              "UPLOAD_DIR": str(tmp_path / "uploads")}
    app = create_app(config)
    with app.app_context():
        upgrade()
    response = app.test_client().post("/api/listings", json=LISTING, headers=auth("alice@unc.edu"))
    assert response.status_code == 201, response.get_json()
    publish_listing(app.test_client(), auth("alice@unc.edu"), response.get_json()["listing"])
    fresh = create_app(config)
    listing = fresh.test_client().get(f"/api/listings/{response.get_json()['listing']['id']}")
    assert listing.get_json()["listing"]["service_duration_minutes"] == 60


def test_empty_sqlite_migrates_for_item_and_service_exchanges(tmp_path):
    app = create_app({
        "TESTING": True, "APP_ENV": "development",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'combined_migration.sqlite'}",
        "AUTH_MODE": "sandbox", "SANDBOX_USERS": ["alice@unc.edu", "bob@unc.edu"],
        "STORAGE_BACKEND": "local", "UPLOAD_DIR": str(tmp_path / "uploads"),
    })
    with app.app_context():
        upgrade()
        assert db.session.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "c707browserroles"
        columns = lambda table: {column["name"] for column in inspect(db.engine).get_columns(table)}
        assert {"service_price_cents", "service_duration_minutes", "service_available_windows", "publication_required", "creation_key"} <= columns("listings")
        assert {"recipient_id", "event_key", "read_at", "created_at"} <= columns("notifications")
        assert {"participant_id", "expires_at", "latitude", "landmark"} <= columns("exchange_locations")
        assert {"latitude", "coordinate_source", "safety_attributes", "safety_checked_at"} <= columns("meeting_spots")
        assert "preferred_meeting_spot_id" in columns("profiles")
        assert {"service_delivery", "service_meeting_spot_id"} <= columns("offer_revisions")
        assert {"service_duration_minutes", "service_time_windows"} <= columns("need_requests")
        assert {"owner_service_confirmed_at", "requester_service_confirmed_at"} <= columns("exchanges")
        assert {"sale_price_cents", "deposit_cents", "service_price_cents", "service_scheduled_at"} <= columns("offer_revisions")
    client = app.test_client()
    alice, bob = auth("alice@unc.edu"), auth("bob@unc.edu")
    item = create_listing(client, alice)
    service = service_listing(client, alice)
    for listing, mode in ((item, "borrow"), (service, "service")):
        response = client.post("/api/exchanges", json={
            "listing_id": listing["id"], "mode": mode,
        }, headers=bob)
        assert response.status_code == 201, response.get_json()


@pytest.mark.parametrize('category', [
    'tutoring', 'proofreading', 'moving help', 'tech help', 'repair and mending',
    'bike repair', 'photography', 'event help',
])
def test_all_supported_service_categories_create_filter_and_match(client, alice, bob, category):
    created = client.post('/api/listings', json={**LISTING, 'category': category,
        'title': 'Demo ' + category}, headers=alice)
    assert created.status_code == 201, created.get_json()
    listing = publish_listing(client, alice, created.get_json()['listing'])
    assert listing['category'] == category
    assert not {'condition', 'collateral_percent', 'sale_price_cents', 'rental_fee_cents'} & listing.keys()
    filtered = client.get('/api/listings', query_string={'mode': 'service', 'category': category})
    assert [row['id'] for row in filtered.get_json()['listings']] == [listing['id']]
    created_request = client.post('/api/requests', json={**REQUEST,
        'normalized': {**REQUEST['normalized'], 'category': category}}, headers=bob)
    assert created_request.status_code == 201, created_request.get_json()
    request_id = created_request.get_json()['request']['id']
    groups = client.get(f'/api/requests/{request_id}/matches', headers=bob).get_json()
    assert [entry['listing_id'] for entry in groups['confirmed']] == [listing['id']]
    assert groups['needs_confirmation'] == []
    assert groups['rejected'] == []


def test_unknown_service_category_rejected_by_listing_and_request_api(client, alice):
    response = client.post('/api/listings', json={**LISTING, 'category': 'other service'}, headers=alice)
    assert response.status_code == 400
    assert 'category' in response.get_json()['error']['fields']
    response = client.post('/api/requests', json={**REQUEST,
        'normalized': {**REQUEST['normalized'], 'category': 'other service'}}, headers=alice)
    assert response.status_code == 400
    assert 'normalized.category' in response.get_json()['error']['fields']
