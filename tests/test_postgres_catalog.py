"""Optional PostgreSQL migration and persistence check on an isolated schema."""

import os
from uuid import uuid4

import pytest
from flask_migrate import upgrade
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from server.app import create_app
from server.db import db
from server.models import Listing, Profile


def _isolated_postgres_target():
    target = os.environ.get("TEST_DATABASE_URL")
    if not target:
        pytest.skip("TEST_DATABASE_URL is not configured")
    test_url = make_url(target)
    if test_url.get_backend_name() != "postgresql" or not (
        test_url.database or ""
    ).endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must target a dedicated PostgreSQL _test database")

    live = os.environ.get("DATABASE_URL")
    if live:
        live_url = make_url(live)
        if test_url.database == live_url.database:
            pytest.fail("TEST_DATABASE_URL must not target DATABASE_URL")
    return target


def test_postgres_migration_and_persistence():
    target = _isolated_postgres_target()
    schema = f"m2_test_{uuid4().hex}"
    admin_engine = create_engine(target)
    schema_created = False
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        schema_created = True

        config = {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": target,
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "connect_args": {"options": f"-csearch_path={schema}"}
            },
        }
        app = create_app(config)
        with app.app_context():
            upgrade()
            owner = Profile(id="postgres-test-owner", display_name="PG test")
            listing = Listing(
                owner=owner,
                title="PostgreSQL test listing",
                category="Test",
                mode="sale",
                sale_price_cents=100,
                status="active",
            )
            db.session.add(listing)
            db.session.commit()
            listing_id = listing.id

        fresh_app = create_app(config)
        response = fresh_app.test_client().get(f"/api/listings/{listing_id}")
        assert response.status_code == 200
        assert response.get_json()["title"] == "PostgreSQL test listing"
    finally:
        if schema_created:
            with admin_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()
