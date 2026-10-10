"""Migration and demo-seed checks carried forward from Person 1 M2."""

from flask_migrate import upgrade
import pytest
from sqlalchemy import func, select

from server.app import create_app
from server.db import db
from server.models import Listing
from tests.conftest import LISTING_BODY, auth


def _migrated_app(tmp_path, database_name, *, app_env="development"):
    config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / database_name}",
        "AUTH_MODE": "sandbox",
        "SANDBOX_USERS": ["alice@unc.edu"],
        "UPLOAD_DIR": str(tmp_path / "uploads"),
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
    assert runner.invoke(args=["seed-demo"]).exit_code == 0
    with app.app_context():
        assert db.session.scalar(select(func.count()).select_from(Listing)) == 2

    other_app = create_app({
        **config,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'not_development.sqlite'}",
    })
    refused = other_app.test_cli_runner().invoke(args=["seed-demo"])
    assert refused.exit_code != 0
    assert "dedicated development database" in refused.output
