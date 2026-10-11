"""Migration and demo-seed checks carried forward from Person 1 M2."""

from flask_migrate import upgrade
import pytest
from sqlalchemy import func, select

from server.app import create_app
from server.db import db
from server.models import Listing
from server.seed import DEMO_SUIT_AVAILABILITY, DEMO_SUIT_TITLE, validate_demo_seed_target
from tests.conftest import LISTING_BODY, auth


def _migrated_app(tmp_path, database_name, *, app_env="development"):
    config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / database_name}",
        "AUTH_MODE": "sandbox",
        "SANDBOX_USERS": ["alice@unc.edu"],
        "UPLOAD_DIR": str(tmp_path / "uploads"),
        "STORAGE_BACKEND": "local",
        "APP_ENV": app_env,
    }
    app = create_app(config)
    with app.app_context():
        upgrade()
    return app, config


def test_migration_and_listing_survive_new_app_instance(tmp_path):
    app, config = _migrated_app(tmp_path, "catalog_test.sqlite")
    created = app.test_client().post(
        "/api/listings", json=LISTING_BODY, headers=auth("alice@unc.edu")
    )
    assert created.status_code == 201, created.get_json()
    listing_id = created.get_json()["listing"]["id"]

    fresh_app = create_app(config)
    response = fresh_app.test_client().get(f"/api/listings/{listing_id}")
    assert response.status_code == 200
    assert response.get_json()["listing"]["title"] == LISTING_BODY["title"]


def test_demo_seed_requires_dev_target_and_is_idempotent(tmp_path):
    app, config = _migrated_app(tmp_path, "seed_dev.sqlite")
    with pytest.raises(RuntimeError, match="AUTH_MODE=supabase"):
        create_app({**config, "APP_ENV": "production"})

    runner = app.test_cli_runner()
    assert runner.invoke(args=["seed-demo"]).exit_code == 0
    with app.app_context():
        suit = db.session.scalar(select(Listing).where(Listing.title == DEMO_SUIT_TITLE))
        original_id = suit.id
        suit.specifications = {**{key: value for key, value in suit.specifications.items() if key != "type"}, "custom_fit": "keep"}
        suit.availability = {"available_from": "2026-10-11T12:00:00Z", "available_until": None, "notes": "custom pickup note"}
        charcoal = db.session.scalar(select(Listing).where(Listing.title.contains("Charcoal suit")))
        charcoal.specifications = {key: value for key, value in charcoal.specifications.items() if key != "type"}
        db.session.commit()
    assert runner.invoke(args=["seed-demo"]).exit_code == 0
    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(Listing)) == 56
        suit = db.session.scalar(select(Listing).where(Listing.title == DEMO_SUIT_TITLE))
        assert suit.id == original_id
        assert suit.specifications["type"] == "suit"
        assert suit.specifications["custom_fit"] == "keep"
        assert suit.availability["available_from"] == "2026-10-11T12:00:00Z"
        assert suit.availability["available_until"] == DEMO_SUIT_AVAILABILITY["available_until"]
        assert suit.availability["notes"] == "custom pickup note"
        charcoal = db.session.scalar(select(Listing).where(Listing.title.contains("Charcoal suit")))
        assert charcoal.specifications["type"] == "suit"

    other_app = create_app({
        **config,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'not_development.sqlite'}",
    })
    refused = other_app.test_cli_runner().invoke(args=["seed-demo"])
    assert refused.exit_code != 0
    assert "dedicated development database" in refused.output


def test_supabase_postgres_seed_requires_explicit_dev_opt_in():
    target = "postgresql+psycopg://postgres.project:password@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    config = {"APP_ENV": "development", "SQLALCHEMY_DATABASE_URI": target, "SUPABASE_URL": "https://project.supabase.co"}
    with pytest.raises(ValueError, match="dedicated development database"):
        validate_demo_seed_target(config)
    validate_demo_seed_target(config, allow_supabase_postgres_dev=True)
    with pytest.raises(ValueError, match="APP_ENV=development"):
        validate_demo_seed_target({**config, "APP_ENV": "production"}, allow_supabase_postgres_dev=True)
    with pytest.raises(ValueError, match="session pooler"):
        validate_demo_seed_target({**config, "SQLALCHEMY_DATABASE_URI": target.replace("/postgres", "/shared")}, allow_supabase_postgres_dev=True)
    with pytest.raises(ValueError, match="session pooler"):
        validate_demo_seed_target({**config, "SQLALCHEMY_DATABASE_URI": target.replace(".pooler.supabase.com", ".example.com")}, allow_supabase_postgres_dev=True)
    with pytest.raises(ValueError, match="session pooler"):
        validate_demo_seed_target({**config, "SQLALCHEMY_DATABASE_URI": target.replace("postgres.project", "postgres")}, allow_supabase_postgres_dev=True)
    with pytest.raises(ValueError, match="session pooler"):
        validate_demo_seed_target({**config, "SQLALCHEMY_DATABASE_URI": target.replace(":5432/", ":6543/")}, allow_supabase_postgres_dev=True)
    with pytest.raises(ValueError, match="session pooler"):
        validate_demo_seed_target({**config, "SUPABASE_URL": "https://different.supabase.co"}, allow_supabase_postgres_dev=True)


def test_seeded_suit_matches_dated_interview_request(tmp_path):
    app, _ = _migrated_app(tmp_path, "interview_dev.sqlite")
    assert app.test_cli_runner().invoke(args=["seed-demo"]).exit_code == 0
    client = app.test_client()
    listings = client.get("/api/listings").get_json()["listings"]
    suit = next(item for item in listings if item["title"] == DEMO_SUIT_TITLE)
    charcoal = next(item for item in listings if "Charcoal suit" in item["title"])
    assert suit["specifications"]["type"] == "suit"
    assert suit["specifications"]["jacket_size"] == "40R"
    assert charcoal["specifications"]["type"] == "suit"
    assert {key: suit["availability"][key] for key in DEMO_SUIT_AVAILABILITY} == DEMO_SUIT_AVAILABILITY

    request_body = {
        "original_text": "Borrow a navy 40R suit for an interview Wednesday, October 14, 2026. Pickup Tuesday 2-4pm; return Thursday by 6pm. Rental budget $40.",
        "normalized": {"source": "manual", "category": "formalwear", "required_specifications": {"type": "suit", "jacket_size": "40R"}, "preferred_specifications": {"color": "navy"}},
        "modes": ["borrow"],
        "budget_cents": 4000,
        "needed_by": "2026-10-14T13:00:00Z",
        "use_start": "2026-10-13T18:00:00Z",
        "use_end": "2026-10-15T22:00:00Z",
        "pickup_windows": [{"start": "2026-10-13T18:00:00Z", "end": "2026-10-13T20:00:00Z"}],
        "area": "Central campus",
    }

    def matches_for(max_deposit_cents):
        created = client.post("/api/requests", json={**request_body, "max_deposit_cents": max_deposit_cents}, headers=auth("alice@unc.edu"))
        assert created.status_code == 201, created.get_json()
        need = created.get_json()["request"]
        assert need["max_deposit_cents"] == max_deposit_cents
        assert all(need[key] == value for key, value in request_body.items())
        response = client.get(f"/api/requests/{need['id']}/matches", headers=auth("alice@unc.edu"))
        assert response.status_code == 200
        result = response.get_json()
        legacy_ids = {suit["id"], charcoal["id"]}
        return {group: [entry for entry in result[group] if entry["listing_id"] in legacy_ids] for group in ("confirmed", "needs_confirmation", "rejected")}

    affordable_80 = matches_for(8000)
    affordable_200 = matches_for(20000)
    assert affordable_80["confirmed"] == []
    assert [entry["listing_id"] for entry in affordable_80["needs_confirmation"]] == [suit["id"]]
    entry = affordable_80["needs_confirmation"][0]
    assert entry["unknown_required"] == ["deposit_agreement"]
    assert any("Required type matches: suit." == reason for reason in entry["reasons"])
    assert any("Required jacket_size matches: 40R." == reason for reason in entry["reasons"])
    assert "Listing availability covers the requested dates." in entry["reasons"]
    assert any("deposit negotiation required" in shortcoming for shortcoming in entry["shortcomings"])
    assert [entry["listing_id"] for entry in affordable_80["rejected"]] == [charcoal["id"]]

    assert [entry["listing_id"] for entry in affordable_200["confirmed"]] == [suit["id"]]
    assert affordable_200["needs_confirmation"] == []
    assert affordable_200["confirmed"][0]["unknown_required"] == []
    assert not any("deposit negotiation" in shortcoming for shortcoming in affordable_200["confirmed"][0]["shortcomings"])
    assert [entry["listing_id"] for entry in affordable_200["rejected"]] == [charcoal["id"]]
