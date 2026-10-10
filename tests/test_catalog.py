"""Public catalog behavior against an isolated, migrated database."""

from flask_migrate import upgrade
from sqlalchemy import func, select

from server.app import create_app
from server.db import db
from server.models import Listing, Profile


def add_listing(app, *, status="active", title="Blue coat"):
    with app.app_context():
        owner = db.session.get(Profile, "private-provider-id")
        if owner is None:
            owner = Profile(
                id="private-provider-id",
                display_name="Alex",
                confirmed_email_domain="unc.edu",
            )
            db.session.add(owner)
        listing = Listing(
            owner=owner,
            title=title,
            category="Clothing",
            description="Warm coat",
            specifications={"size": "M"},
            condition="Good",
            accessories=None,
            mode="sale",
            sale_price_cents=2400,
            status=status,
        )
        db.session.add(listing)
        db.session.commit()
        return listing.id


def test_public_list_and_detail_exclude_private_profile(db_app, db_client):
    listing_id = add_listing(db_app)

    response = db_client.get("/api/listings")
    assert response.status_code == 200
    assert response.is_json
    body = response.get_json()
    assert body["page"] == 1
    assert body["per_page"] == 20
    assert body["total"] == 1
    assert len(body["items"]) == 1

    public = body["items"][0]
    assert public["id"] == listing_id
    assert public["title"] == "Blue coat"
    assert public["modes"] == ["sale"]
    assert public["sale_price_cents"] == 2400
    assert public["rental_fee_cents"] is None
    assert public["owner_display_name"] == "Alex"
    assert public["created_at"].endswith("Z")
    assert "owner_id" not in public
    assert "confirmed_email_domain" not in public
    assert "private-provider-id" not in response.get_data(as_text=True)
    assert "unc.edu" not in response.get_data(as_text=True)

    detail = db_client.get(f"/api/listings/{listing_id}")
    assert detail.status_code == 200
    assert detail.get_json() == public


def test_nonpublic_and_missing_listings_are_concealed(db_app, db_client):
    draft_id = add_listing(db_app, status="draft")

    assert db_client.get("/api/listings").get_json()["items"] == []
    for listing_id in (draft_id, "missing"):
        response = db_client.get(f"/api/listings/{listing_id}")
        assert response.status_code == 404
        assert response.get_json()["error"]["code"] == "not_found"


def test_pagination_and_invalid_input(db_app, db_client):
    add_listing(db_app, title="First")
    add_listing(db_app, title="Second")

    first_page = db_client.get("/api/listings?per_page=1&page=1").get_json()
    second_page = db_client.get("/api/listings?per_page=1&page=2").get_json()
    assert first_page["total"] == second_page["total"] == 2
    assert len(first_page["items"]) == len(second_page["items"]) == 1
    assert first_page["items"][0]["id"] != second_page["items"][0]["id"]

    for query in ("page=0", "page=1.5", "per_page=0", "per_page=51"):
        response = db_client.get(f"/api/listings?{query}")
        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "invalid_input"


def test_records_survive_a_new_application_instance(db_app):
    listing_id = add_listing(db_app)
    uri = db_app.config["SQLALCHEMY_DATABASE_URI"]

    fresh_app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": uri})
    response = fresh_app.test_client().get(f"/api/listings/{listing_id}")

    assert response.status_code == 200
    assert response.get_json()["title"] == "Blue coat"


def test_catalog_without_database_configuration_returns_service_error(client):
    response = client.get("/api/listings")
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "database_unavailable"


def test_demo_seed_requires_dev_target_and_is_idempotent(tmp_path):
    database_path = tmp_path / "seed_dev.sqlite"
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
    })
    with app.app_context():
        upgrade()

    runner = app.test_cli_runner()
    assert runner.invoke(args=["seed-demo"], env={"APP_ENV": "production"}).exit_code != 0
    assert runner.invoke(args=["seed-demo"], env={"APP_ENV": "development"}).exit_code == 0
    assert runner.invoke(args=["seed-demo"], env={"APP_ENV": "development"}).exit_code == 0
    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(Profile)) == 1
        assert db.session.scalar(select(func.count()).select_from(Listing)) == 1
    assert app.test_client().get("/api/listings").get_json()["items"][0]["is_demo"] is True

    wrong_name = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'not_development.sqlite'}",
    })
    assert wrong_name.test_cli_runner().invoke(
        args=["seed-demo"], env={"APP_ENV": "development"}
    ).exit_code != 0
